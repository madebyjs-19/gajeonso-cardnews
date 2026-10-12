"""Gemini text/vision requests. Bounded transient retries; no alternate providers."""
import json
from copy import deepcopy
import os
import random
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from ai_efficiency import ACTIVE, QuotaPause
from git_checkpoint import CheckpointError

MODEL = 'gemini-3.8-flash'
BASE = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODEL
_last_request = None


class GeminiFailure(RuntimeError):
    """Only controlled diagnostic codes; never keep API bodies or credentials."""
    def __init__(self, code, http_status=None):
        self.code = code
        self.http_status = http_status
        super().__init__('Gemini content request failed; ' + code)


def request_json(request, timeout=180):
    """Retry only transient transport/server failures, at most three requests.

    Never retry quota/auth/input errors or publication APIs. No raw API body is logged.
    """
    global _last_request
    for attempt in range(3):
        if _last_request is not None:
            time.sleep(max(0, 15 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        if request.data is not None and ACTIVE.get() is not None:
            ACTIVE.get().reserve()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as stream:
                return json.load(stream)
        except urllib.error.HTTPError as exc:
            if exc.code not in (408, 500, 502, 503, 504) or attempt == 2:
                raise
            status = exc.code
        except (TimeoutError, socket.timeout, urllib.error.URLError):
            if attempt == 2:
                raise
            status = None
        delay = 20 * (2 ** attempt) + random.uniform(0, 3)
        reason = f'서버 응답 코드 {status}' if status else '연결 또는 응답 지연'
        print(f'제미나이 {reason}: {round(delay)}초 후 재시도합니다. ({attempt + 2}/3)', flush=True)
        time.sleep(delay)


def check_model():
    try:
        request = urllib.request.Request(BASE, headers={'x-goog-api-key': os.environ['GEMINI_API_KEY']})
        model = request_json(request, timeout=30)
        if model.get('name') != 'models/' + MODEL or 'generateContent' not in model.get('supportedGenerationMethods', []):
            raise RuntimeError()
    except Exception:
        raise ValueError('Gemini key or model access check failed') from None


def response(input_items, schema=None):
    global _last_request
    try:
        instructions, contents = [], []
        for item in input_items:
            value = item['content']
            if item['role'] in ('developer', 'system'):
                instructions.append({'text': value})
                continue
            parts = []
            for part in ([{'type': 'input_text', 'text': value}] if isinstance(value, str) else value):
                if part['type'] == 'input_text':
                    parts.append({'text': part['text']})
                elif part['type'] == 'input_image':
                    prefix, encoded = part['image_url'].split(',', 1)
                    if prefix != 'data:image/jpeg;base64':
                        raise ValueError()
                    parts.append({'inlineData': {'mimeType': 'image/jpeg', 'data': encoded}})
                else:
                    raise ValueError()
            contents.append({'role': 'user', 'parts': parts})
        config = {'maxOutputTokens': 7000 if schema and 'deck' in schema.get('properties', {}) else 2500,
                  'thinkingConfig': {'thinkingLevel': 'LOW'}}
        if schema:
            config.update(responseMimeType='application/json', responseJsonSchema=schema)
        payload = {'contents': contents, 'generationConfig': config}
        if instructions:
            payload['systemInstruction'] = {'parts': instructions}
        session = ACTIVE.get()
        cache_key = session.key({'model': MODEL, 'payload': payload}) if session else None
        if session and cache_key in session.cache['responses']:
            return deepcopy(session.cache['responses'][cache_key])
        request = urllib.request.Request(BASE + ':generateContent', json.dumps(payload).encode(),
                                         {'x-goog-api-key': os.environ['GEMINI_API_KEY'], 'Content-Type': 'application/json'})
        result = request_json(request)
        if result.get('promptFeedback', {}).get('blockReason'):
            raise GeminiFailure('blocked')
        if not result.get('candidates'):
            raise GeminiFailure('empty')
        candidate = result['candidates'][0]
        if candidate.get('finishReason') == 'MAX_TOKENS':
            raise GeminiFailure('truncated')
        if candidate.get('finishReason') != 'STOP':
            raise GeminiFailure('incomplete')
        text = '\n'.join(p['text'] for p in candidate['content']['parts'] if 'text' in p and not p.get('thought'))
        if not text.strip():
            raise GeminiFailure('empty')
        if schema:
            import jsonschema
            try:
                value = json.loads(text)
                jsonschema.validate(value, schema)
            except (json.JSONDecodeError, jsonschema.ValidationError):
                raise GeminiFailure('schema') from None
            if session:
                session.remember(cache_key, value)
            return value
        if session:
            session.remember(cache_key, text)
        return text
    except (GeminiFailure, QuotaPause, CheckpointError):
        raise
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            # Inspect only known quota identifiers; never retain or log raw bodies.
            try:
                body = json.loads(exc.read(65536))
                violations = [v for d in body.get('error', {}).get('details', [])
                              for v in d.get('violations', [])]
                ids = ' '.join(str(v.get('quotaId', '')) for v in violations).lower()
            except Exception:
                ids = ''
            if 'perday' in ids:
                kind = 'daily'
            elif 'perminute' in ids:
                retry = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat()
                raise QuotaPause('minute', retry) from None
            else:
                kind = 'unknown'
            if ACTIVE.get():
                ACTIVE.get().pause(kind)
            raise QuotaPause(kind) from None
        code = ('auth' if exc.code in (401, 403) else
                'request' if exc.code == 400 else
                'model' if exc.code == 404 else
                'server' if 500 <= exc.code < 600 else 'http')
        raise GeminiFailure(code, http_status=exc.code) from None
    except (TimeoutError, socket.timeout):
        raise GeminiFailure('timeout') from None
    except urllib.error.URLError:
        raise GeminiFailure('network') from None
    except Exception:
        raise RuntimeError('Gemini content request failed; nothing approved or published') from None
