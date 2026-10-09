"""Gemini text/vision requests. No search tools, alternate providers or retries."""
import json
import os
import time
import urllib.error
import urllib.request

MODEL = 'gemini-3.8-flash'
BASE = 'https://generativelanguage.googleapis.com/v1beta/models/' + MODEL
_last_request = None


def check_model():
    try:
        request = urllib.request.Request(BASE, headers={'x-goog-api-key': os.environ['GEMINI_API_KEY']})
        with urllib.request.urlopen(request, timeout=30) as stream:
            model = json.load(stream)
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
        config = {'maxOutputTokens': 12000, 'thinkingConfig': {'thinkingLevel': 'LOW'}}
        if schema:
            config.update(responseMimeType='application/json', responseJsonSchema=schema)
        payload = {'contents': contents, 'generationConfig': config}
        if instructions:
            payload['systemInstruction'] = {'parts': instructions}
        # Space the five daily requests; free quotas vary by project and can be zero.
        if _last_request is not None:
            time.sleep(max(0, 15 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        request = urllib.request.Request(BASE + ':generateContent', json.dumps(payload).encode(),
                                         {'x-goog-api-key': os.environ['GEMINI_API_KEY'], 'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=480) as stream:
            result = json.load(stream)
        candidate = result['candidates'][0]
        if candidate.get('finishReason') != 'STOP' or result.get('promptFeedback', {}).get('blockReason'):
            raise RuntimeError()
        text = '\n'.join(p['text'] for p in candidate['content']['parts'] if 'text' in p and not p.get('thought'))
        if not text.strip():
            raise RuntimeError()
        if schema:
            import jsonschema
            value = json.loads(text)
            jsonschema.validate(value, schema)
            return value
        return text
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError('Gemini free quota unavailable or exhausted; no fallback, approval or publication') from None
        raise RuntimeError('Gemini content request failed; nothing approved or published') from None
    except Exception:
        raise RuntimeError('Gemini content request failed; nothing approved or published') from None
