"""Read official Korean newsroom sources without a paid search API."""
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import json
import re
import urllib.request
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

DOMAINS = ['samsung.com', 'lg.com', 'lge.co.kr', 'e-himart.co.kr', 'energy.or.kr', 'kepco.co.kr', 'go.kr']
SAMSUNG = 'https://news.samsung.com/kr/feed'
LG = 'https://apiv2.lge.co.kr/displaysvc/ajax/v1/story/newsroom-list'
KEYWORDS = ('가전', '냉장고', '세탁', '건조', '청소', '식기', '에어컨', '히트펌프', 'TV', '티비', '텔레비전', '아트 스토어', '구독', '공기청정')


def allowed(url):
    p = urlparse(url)
    host = p.hostname or ''
    return (p.scheme == 'https' and p.port in (None, 443) and not p.username and not p.password
            and any(host == d or host.endswith('.' + d) for d in DOMAINS))


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Source redirect left official domains')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def read(url):
    if not allowed(url):
        raise ValueError('Source must use an official HTTPS domain')
    request = urllib.request.Request(url, headers={'User-Agent': 'Gajeonso-cardnews/1.0', 'Origin': 'https://www.lge.co.kr'})
    with urllib.request.build_opener(OfficialRedirect()).open(request, timeout=30) as stream:
        raw = stream.read(3_000_001)
        if len(raw) > 3_000_000:
            raise ValueError('Source document too large')
        return raw.decode('utf-8')


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def clean(value):
    parser = Text()
    parser.feed(value)
    return re.sub(r'\s+', ' ', ' '.join(parser.parts)).strip()


def recent_sources(run):
    end = datetime.strptime(run, '%Y%m%d').replace(tzinfo=ZoneInfo('Asia/Seoul')) + timedelta(days=1)
    start = end - timedelta(days=15)
    candidates, warnings = [], []
    try:
        for item in ET.fromstring(read(SAMSUNG)).findall('.//item'):
            body = item.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or item.findtext('description') or ''
            candidates.append(dict(title=clean(item.findtext('title') or ''), source_url=item.findtext('link'),
                                   published=parsedate_to_datetime(item.findtext('pubDate')), text=clean(body)))
    except Exception:
        warnings.append('삼성 공식 RSS 수집 실패')
    try:
        for item in json.loads(read(LG))['data']['list']:
            candidates.append(dict(title=clean(item['newsTitleText']),
                                   source_url='https://www.lge.co.kr/story/newsroom/' + str(int(item['postId'])),
                                   published=datetime.strptime(item['postDate'], '%Y.%m.%d').replace(tzinfo=ZoneInfo('Asia/Seoul')),
                                   text=clean(item.get('newsContent') or item['newsContentText'])))
    except Exception:
        warnings.append('LG 공식 뉴스룸 수집 실패')
    sources, seen = [], set()
    for c in sorted(candidates, key=lambda c: c['published'], reverse=True):
        url = c['source_url']
        if (not url or not allowed(url) or url in seen or not start <= c['published'] < end
                or not any(k in c['title'] + c['text'] for k in KEYWORDS) or len(c['text']) < 300):
            continue
        seen.add(url)
        sources.append(dict(title=c['title'], source_url=url, published=c['published'].isoformat(), text=c['text'][:16000]))
        if len(sources) == 12:
            break
    if len(sources) < 2:
        raise ValueError('Insufficient recent official appliance sources; no generation or publication')
    return sources, warnings


def recheck(facts, sources):
    known = {s['source_url'] for s in sources}
    urls = list(dict.fromkeys(f['source_url'] for f in facts))
    if len(urls) > 8 or any(url not in known for url in urls):
        raise ValueError('Facts must cite retrieved official articles; invented sources are rejected')
    documents = []
    for url in urls:
        try:
            text = clean(read(url))
            if len(text) < 300:
                raise ValueError()
            documents.append(dict(source_url=url, text=text[:24000]))
        except Exception:
            raise ValueError('Official fact source could not be re-read; no approval or publication') from None
    return documents
