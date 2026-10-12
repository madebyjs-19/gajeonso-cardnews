"""Accept externally researched, rendered and reviewed deliverables without AI calls.

This is a handoff, not a review bypass: the producer must inspect the actual five
images, document its source review and bind that review to every delivered byte.
Telegram approval and all publication protections remain in the existing worker.
"""
import hashlib
import json
from PIL import Image

from content_pipeline import validate_content
from publish_state import validate_run

FILES = tuple([f'card{i}.jpg' for i in range(1, 6)] +
              ['reel.mp4', 'caption_ig.txt', 'caption_fb.txt', 'content.json', 'brief.json'])


def available(root, run):
    return (root / 'cards' / run / 'review.json').is_file()


def load_prepared(root, run):
    validate_run(run)
    directory = root / 'cards' / run
    review = json.loads((directory / 'review.json').read_text(encoding='utf-8'))
    if (review.get('version') != 1 or review.get('run') != run
            or review.get('reviewer') != 'ChatGPT'
            or review.get('fact_review') is not True
            or review.get('visual_review') is not True
            or review.get('inspected_cards') != [1, 2, 3, 4, 5]
            or not review.get('checked_at') or not review.get('notes')):
        raise ValueError('Prepared content review missing or incomplete')
    if set(review.get('sha256', {})) != set(FILES):
        raise ValueError('Prepared content file manifest incomplete')
    for name in FILES:
        path = directory / name
        if (not path.is_file() or path.is_symlink() or not path.stat().st_size
                or hashlib.sha256(path.read_bytes()).hexdigest() != review['sha256'][name]):
            raise ValueError('Prepared content changed after review')
    for i in range(1, 6):
        with Image.open(directory / f'card{i}.jpg') as image:
            if image.format != 'JPEG' or image.size != (1080, 1350):
                raise ValueError('Invalid output dimensions')
            image.verify()
    content = json.loads((directory / 'content.json').read_text(encoding='utf-8'))
    validate_content(content)
    for platform in ('ig', 'fb'):
        if (directory / f'caption_{platform}.txt').read_text(encoding='utf-8') != content[f'caption_{platform}']:
            raise ValueError('Prepared captions differ from reviewed content')
    brief = json.loads((directory / 'brief.json').read_text(encoding='utf-8'))
    for key in ('topic', 'type', 'facts', 'warnings', 'reason', 'candidates'):
        if brief.get(key) != content[key]:
            raise ValueError('Prepared brief differs from reviewed content')
    if (brief.get('cover') != content['deck']['cover_color']
            or brief.get('card_types') != [c['type'] for c in content['deck']['cards'][1:4]]
            or brief.get('source_method') != 'chatgpt_reviewed'
            or brief.get('fact_qa', {}).get('passed') is not True
            or brief.get('visual_qa', {}).get('passed') is not True):
        raise ValueError('Prepared brief review missing or incomplete')
    return brief
