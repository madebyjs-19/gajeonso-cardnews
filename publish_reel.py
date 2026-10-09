# Usage: python3.13 publish_reel.py YYYYMMDD caption_ig.txt caption_fb.txt
"""Publish approved reels independently of card publication results."""
from publish_common import main

if __name__ == '__main__':
    raise SystemExit(main(reel=True))
