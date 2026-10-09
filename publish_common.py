"""Shared publishing runner; never automatically retry a visible publish request."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from publish_state import BLOCKED, ROOT, locked_state

G = 'https://graph.facebook.com/v26.0'
RAW = 'https://raw.githubusercontent.com/madebyjs-19/gajeonso-cardnews/main/cards'


def call(method, path, headers=None, **params):
    url = path if path.startswith('https://') else G + path
    data = urllib.parse.urlencode(params).encode() if method == 'POST' else None
    if method == 'GET':
        url += '?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data, headers or {}, method=method), timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Error bodies and URLs can contain credentials. Never print or persist them.
        raise RuntimeError('Meta HTTP error ' + str(exc.code)) from None


def need(response, field=None):
    if not isinstance(response, dict) or 'error' in response:
        raise RuntimeError('Meta rejected request')
    if field and not response.get(field):
        raise RuntimeError('Meta response missing ' + field)
    return response[field] if field else response


def wait(container, token, attempts=24):
    for _ in range(attempts):
        status = need(call('GET', '/' + container, fields='status_code', access_token=token), 'status_code')
        if status == 'FINISHED':
            return
        if status in ('ERROR', 'EXPIRED', 'PUBLISHED'):
            raise RuntimeError('Container unavailable')
        time.sleep(5)
    raise RuntimeError('Container timeout')


def publish_visible(state, channel, method, path, field='id', status='success', **params):
    # Write-ahead marker survives a process crash, timeout or missing response ID.
    # Even a definite API rejection remains blocked until an operator reconciles it.
    state.set_channel(channel, 'publishing')
    response = need(call(method, path, **params))
    if field == 'success':
        if response.get('success') is not True:
            raise RuntimeError('Publish not acknowledged')
        media_id = state.data['channels'][channel]['video_id']
    else:
        media_id = str(need(response, field))
    state.set_channel(channel, status, media_id=media_id)
    return media_id


def permalink(state, channel, media_id, token, field):
    try:
        link = need(call('GET', '/' + media_id, fields=field, access_token=token)).get(field)
        if link:
            # Store only canonical platform URLs, never arbitrary echoed response data.
            parsed = urllib.parse.urlparse(link)
            if parsed.scheme == 'https' and parsed.hostname in ('www.instagram.com', 'instagram.com', 'www.facebook.com', 'facebook.com') and not parsed.query:
                state.set_channel(channel, state.data['channels'][channel]['status'], permalink=link)
    except Exception:
        pass  # Successful publication must remain successful when lookup fails.


def instagram(state, caption, token, user, reel=False):
    channel = 'ig_reel' if reel else 'ig_card'
    if reel:
        container = str(need(call('POST', f'/{user}/media', media_type='REELS',
                                 video_url=f'{RAW}/{state.run}/reel.mp4', caption=caption,
                                 share_to_feed='true', access_token=token), 'id'))
    else:
        children = []
        for i in range(1, 6):
            cid = str(need(call('POST', f'/{user}/media', image_url=f'{RAW}/{state.run}/card{i}.jpg',
                                is_carousel_item='true', access_token=token), 'id'))
            children.append(cid)
            state.set_channel(channel, 'preparing', children=children[:])
        for cid in children:
            wait(cid, token)
        container = str(need(call('POST', f'/{user}/media', media_type='CAROUSEL',
                                 children=','.join(children), caption=caption, access_token=token), 'id'))
    state.set_channel(channel, 'preparing', container_id=container)
    wait(container, token, 60 if reel else 24)
    mid = publish_visible(state, channel, 'POST', f'/{user}/media_publish', creation_id=container, access_token=token)
    permalink(state, channel, mid, token, 'permalink')


def facebook(state, caption, token, page, reel=False):
    channel = 'fb_reel' if reel else 'fb_card'
    if reel:
        start = need(call('POST', f'/{page}/video_reels', upload_phase='start', access_token=token))
        vid = str(need(start, 'video_id'))
        upload_url = need(start, 'upload_url')
        parsed = urllib.parse.urlparse(upload_url)
        if parsed.scheme != 'https' or parsed.hostname != 'rupload.facebook.com':
            raise RuntimeError('Unexpected upload host')
        state.set_channel(channel, 'preparing', video_id=vid)
        need(call('POST', upload_url, headers={'Authorization': 'OAuth ' + token,
                                              'file_url': f'{RAW}/{state.run}/reel.mp4'}))
        time.sleep(10)
        publish_visible(state, channel, 'POST', f'/{page}/video_reels', field='success', status='submitted',
                        upload_phase='finish', video_id=vid, video_state='PUBLISHED', description=caption, access_token=token)
        # Meta acknowledged the request; do not claim that processing has completed.
        state.set_channel(channel, 'submitted', permalink='https://www.facebook.com/reel/' + vid)
    else:
        photos = []
        for i in range(1, 6):
            photos.append(str(need(call('POST', f'/{page}/photos', url=f'{RAW}/{state.run}/card{i}.jpg',
                                        published='false', access_token=token), 'id')))
            state.set_channel(channel, 'preparing', photos=photos[:])
        media = {f'attached_media[{i}]': json.dumps({'media_fbid': pid}) for i, pid in enumerate(photos)}
        mid = publish_visible(state, channel, 'POST', f'/{page}/feed', message=caption, access_token=token, **media)
        permalink(state, channel, mid, token, 'permalink_url')


def verify_remote_media(state, reel):
    """Meta fetches main, so approval must cover exactly those publicly hosted bytes."""
    names = ['reel.mp4'] if reel else [f'card{i}.jpg' for i in range(1, 6)]
    for name in names:
        local = state.root / 'cards' / state.run / name
        expected = hashlib.sha256(local.read_bytes()).digest()
        digest, count = hashlib.sha256(), 0
        with urllib.request.urlopen(f'{RAW}/{state.run}/{name}', timeout=90) as response:
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                count += len(chunk)
                if count > local.stat().st_size:
                    raise ValueError('Hosted media differs from approved media')
                digest.update(chunk)
        if digest.digest() != expected:
            raise ValueError('Hosted media differs from approved media')


def notify(text):
    if not os.environ.get('TELEGRAM_BOT_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID'):
        return False
    try:
        with urllib.request.urlopen('https://api.telegram.org/bot' + os.environ['TELEGRAM_BOT_TOKEN'] + '/sendMessage',
                                    urllib.parse.urlencode({'chat_id': os.environ['TELEGRAM_CHAT_ID'], 'text': text}).encode(), timeout=30):
            pass
        return True
    except Exception:
        return False


def main(reel=False):
    parser = argparse.ArgumentParser()
    parser.add_argument('run')
    parser.add_argument('ig_caption')
    parser.add_argument('fb_caption')
    args = parser.parse_args()
    try:
        captions = [Path(p).read_text(encoding='utf-8') for p in (args.ig_caption, args.fb_caption)]
        with locked_state(args.run) as state:
            state.save()  # Import legacy success markers before doing anything remote.
            state.require_approval(captions)
            pending = [p + ('_reel' if reel else '_card') for p in ('ig', 'fb')]
            if any(state.data['channels'].get(c, {}).get('status') not in BLOCKED for c in pending):
                verify_remote_media(state, reel)
            results, failed = [], False
            for platform, fn, caption, token_name, id_name in (
                    ('ig', instagram, captions[0], 'IG_ACCESS_TOKEN', 'IG_USER_ID'),
                    ('fb', facebook, captions[1], 'FB_PAGE_ACCESS_TOKEN', 'FB_PAGE_ID')):
                channel = platform + ('_reel' if reel else '_card')
                item = state.data['channels'].get(channel, {})
                if item.get('status') in BLOCKED:
                    results.append(channel + ': skipped (' + item['status'] + ')')
                    failed |= item['status'] in ('unknown', 'publishing')
                    continue
                if not os.environ.get(token_name) or not os.environ.get(id_name):
                    state.set_channel(channel, 'skipped', reason='missing_configuration')
                    failed = True
                else:
                    state.set_channel(channel, 'preparing', account_id=os.environ[id_name])
                    try:
                        fn(state, caption, os.environ[token_name], os.environ[id_name], reel=reel)
                    except Exception as exc:
                        current = state.data['channels'][channel]['status']
                        # Persist failure stage, but never raw exception text or secrets.
                        if current not in ('success', 'submitted'):
                            state.set_channel(channel, 'unknown' if current == 'publishing' else 'failed',
                                              error_type=type(exc).__name__)
                        failed = True
                item = state.data['channels'][channel]
                results.append(channel + ': ' + item['status'] + (' ' + item['permalink'] if item.get('permalink') else ''))
            msg = '[' + args.run + (' 릴스 결과' if reel else ' 카드 결과') + ']\n' + '\n'.join(results)
            print(msg)
            if not notify(msg):
                print('TELEGRAM_NOTIFICATION_FAILED (publish state preserved)')
            return 1 if failed else 0
    except (ValueError, OSError, KeyError, urllib.error.URLError) as exc:
        # All ValueErrors raised by this module/state are controlled, credential-free messages.
        print(str(exc) if isinstance(exc, ValueError) else 'Pre-flight failed: ' + type(exc).__name__)
        return 1
