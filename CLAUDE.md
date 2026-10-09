# 가전소 카드뉴스 작업 규칙 (스케줄 실행 시 반드시 적용)

## 표지 이미지 규칙 (모든 유형 A~D 공통)
- 모든 게시물의 1장 표지에는 주제에 맞는 제품 이미지를 넣는다. 제품이 주인공이 아닌 주제(제도·서비스·행사 안내 등)도 예외가 아니다.
- 이미지가 필요한 표지는 `product_cover` 카드로 만든다(`label`, `title`, `subtitle`, `image`).
  - 1순위: 공식·신뢰 출처의 실물 사진(step2_5 절차대로 내려받아 배경 제거, 출처 URL 기록, 사용권 불분명 시 승인 메시지에 "이미지 사용권 확인 필요" 명시).
  - 2순위(실물을 못 구했거나 주제를 대표하는 특정 제품이 없을 때): `"image": "illust:종류"` 일러스트. 종류는 주제와 가장 가까운 제품군으로 고른다(fridge, kimchi_fridge, washer, dryer, tv, aircon, air_purifier, stick_vacuum, robot_vacuum, microwave, dishwasher, generic).
  - 일러스트 사용 시 승인 메시지에 "제품 이미지: 일러스트 사용"이라고 적는다.
- 표지 이후 로고는 `stamp_logo.py`로 합성한다. 이미지·제목·로고가 겹치지 않는지 직접 확인한다.
- 유형 C(포스터형)는 `poster`의 `image` 항목을 쓴다.

## 릴스 (매 회차 적용)
- 카드 5장 완성·로고 합성 후 `python3.13 make_reel.py out/YYYYMMDD` 로 하이라이트 릴스(1,2,3,5장, 약 12초)를 만든다. 카드 구성상 다른 장이 핵심이면 `make_reel.py out/YYYYMMDD 1,2,4,5`처럼 장 번호를 지정한다.
- `out/YYYYMMDD/reel.mp4` 를 `cards/YYYYMMDD/reel.mp4` 로 복사해 카드와 함께 커밋·푸시하고, 텔레그램 승인 요청에 sendVideo 로 미리보기를 함께 보낸다.
- 승인 후 카드 발행(`publish.py`)에 이어 `python3.13 publish_reel.py YYYYMMDD ig캡션.txt fb캡션.txt` 로 Instagram·Facebook 릴스를 올린다. 릴스 실패는 카드 발행 결과와 별도로 보고·로그한다.
- 로그에는 결과 칸에 "IG 릴스 성공/실패", "FB 릴스 성공/실패"를 함께 적는다.

## 발행
- 발행은 `python3.13 publish.py YYYYMMDD ig캡션.txt fb캡션.txt` 로 한다(텔레그램 승인 후에만).
- 카드 생성·로고 합성은 `python3.13` 으로 실행한다(Pillow·numpy·qrcode가 python3.13에 설치됨).
- `deck.json`, `fonts/`, `out/`, `img/` 는 커밋하지 않는다(.gitignore 등록됨).
