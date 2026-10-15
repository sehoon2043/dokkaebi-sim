# dokkaebi-sim

도사 수첩(https://sehoon2043.github.io/dokkaebi-dosa/) 자동 분석. 저장 서버에서 새로 저장된 프로필을 받아 추천 트리를 계산해 돌려준다.

- `analyze.py` — 대기 프로필 처리(검증은 여러 프로세스로 병렬, 진행률을 서버에 보고). 로컬 테스트: `python analyze.py --local 프로필.json`
- `sim/timeline.py` — 도술 시전 시간표 시뮬레이터(스타일 신식 포함)
- `sim/field.py` — 필드 처치 속도·보스 DPS 모델(허수아비 실측 보정), `sim/mob.py` — 몰이(몹 5마리) 모델(비경 실측 보정)
- `sim/verify.py` — 추천 트리 검증(한 칸 바꾼 조합 비교·가정 흔들기)과 탐색 보강, `sim/explain.py` — 포인트 문구
- `sim/gamedata.py` — 게임 데이터 읽기. 도술 수치표·각성 표는 저장소에 넣지 않고 저장 서버에서 받는다(`DOSA_URL`·`DOSA_KEY` 필요). `data/targets.json`은 도술 대상 수
- `tools/check.py` — 계산 자동 점검(`--quick`은 분석 전에, 전체는 계산 코드 push 때 `check.yml`)
- `tools/mksite.py` — 사이트(index.html) 생성, `tools/community/` — 커뮤니티 소식 정리
- `server/` — 저장 서버(Vercel + Upstash Redis). 저장하면 GitHub Actions 분석을 요청한다
- GitHub Actions: 저장 직후 실행, 예비로 매일 한국 시간 오전 9시·밤 9시. 시크릿 `DOSA_URL`(저장 서버 주소), `DOSA_KEY`(관리 키)
