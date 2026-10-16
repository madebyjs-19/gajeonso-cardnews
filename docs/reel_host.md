# 릴스 고정 진행자 기준 이미지 만들기

모든 릴스에 같은 사람이 나오게 하려고, 한 번만 진행자 기준 이미지를 만들어 `assets/reel_host/` 에 넣어 둡니다.
파일이 있으면 Actions 가 매 회차 텔레그램으로 같이 보내 주고, Flow 에서 영상을 만들 때 '재료(Ingredients)'로 넣으면 됩니다.

## 1. Flow(또는 다른 이미지 생성 도구)에서 아래 프롬프트로 이미지 만들기

```
Character reference sheet, photorealistic, plain light gray studio background, soft even lighting.
A Korean woman in her early 30s, chin-length straight black bob with blunt bangs, round thin black-rimmed glasses, warm bright smile, natural makeup.
She wears a crisp white lab coat over a navy crew-neck top, a small orange pen clipped to the chest pocket, and a plain blank badge on a navy lanyard. Slim, medium height.
Left: front view, waist-up, looking at the camera. Right: full-body three-quarter view, pointing to the right with one hand.
No text, no letters, no logos, no watermark.
```

마음에 드는 한 장이 나올 때까지 다시 만들어도 됩니다. 이 이미지가 앞으로 계속 쓰일 '얼굴'입니다.

## 2. 저장소에 넣기

- 고른 이미지를 `assets/reel_host/host.jpg`(또는 .png) 로 저장해 main 에 올립니다(최대 3장까지 전송됨).
- 진행자 외모를 바꾸고 싶으면 이 이미지와 ROUTINE_PROMPT.md step3 7번의 HOST 문단을 함께 바꿉니다(둘이 다르면 인물이 흔들립니다).
