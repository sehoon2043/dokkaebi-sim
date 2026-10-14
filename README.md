# dokkaebi-sim

도사 수첩 자동 분석(비공개). 구글 시트(Apps Script)에 저장된 프로필 중 새로 바뀐 것만 받아 추천 트리를 계산해 돌려준다.

- `analyze.py` — 대기 프로필 처리. 로컬 테스트: `python analyze.py --local 프로필.json`
- `sim/verify.py` — 추천 트리 검증(한 칸 바꾼 조합 비교·가정 흔들기)과 탐색 보강
- `tools/check.py` — 계산 자동 점검(Actions에서 분석 전에 실행, 실패하면 분석 안 함)
- `sim/mob.py` — 몰이(몹 5마리) 모델, `sim/field.py` — 필드 처치 속도·보스 DPS 모델, `sim/jmodel.py` — 스타일 기전 포함 도술 시뮬레이터
- `data/skills.json` — 10/14 패치 후 인게임 툴팁 0강 환산 계수, `data/targets.json` — 도술 대상 수
- `tools/mksite.py` — 사이트(index.html) 생성
- GitHub Actions: 매일 한국 시간 오전 9시·밤 9시 실행. 시크릿 `DOSA_URL`(웹 앱 URL), `DOSA_KEY`(관리 키)
