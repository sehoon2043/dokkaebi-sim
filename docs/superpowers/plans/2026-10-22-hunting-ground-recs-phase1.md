# 사이트 개편 1단계 (사냥터별 추천 빌드) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사이트를 [내 수첩]/[추천 빌드] 탭 2개로 나누고, 사냥터 → 광역/단일 → 생존·믹스·딜 카드 3장(계산 1위 + 커뮤니티 빌드, 도술 아이콘)을 보여 주며, 고른 빌드를 재계산 없이 즉시 저장한다.

**Architecture:** 계산 쪽은 순수 함수 모듈 3개(`sim/sustain.py` 유지력, `sim/tiers.py` 등급별 1위, `sim/decks.py` 커뮤니티 덱 분류)를 새로 만들고, `analyze.py`가 기존 탐색 결과(R)를 씨앗으로 써서 결과에 `grounds`·`decks`·`unassigned`를 더한다. 저장 서버에는 재계산 없는 `pick` 요청을 더한다. 사이트는 새 화면 코드를 `site/builds.js`·`site/builds.css`로 따로 두고 `tools/mksite.py`가 끼워 넣는다.

**Tech Stack:** Python 3.12(표준 라이브러리만), Node 24(Vercel Functions, `@upstash/redis`), 바닐라 JS(사이트, 빌드 도구 없음)

**Spec:** `docs/superpowers/specs/2026-10-22-hunting-ground-recs-design.md` (12장 1단계). 실행하는 사람은 계획과 설계 문서를 둘 다 읽는다.

## Global Constraints

- 코드 스타일은 주변 코드와 같게: 파이썬·JS 모두 짧은 한국어 주석, 기존 이름 짓기 방식(`F`, `M`, `S` 모듈 별칭 등).
- 테스트 장치는 `tools/check.py`(새 파이썬 테스트 프레임워크를 만들지 않는다). 새 점검은 `ok(cond, msg)` 방식으로 섹션 함수에 넣는다.
- 공개 저장소·Actions 실행 기록·공개 JSON(`community.json`, 결과 예시)에 닉네임 같은 개인 정보를 남기지 않는다.
- `data/skills.json`·`data/transcend.json`은 저장소에 넣지 않는다(.gitignore 그대로).
- 계산을 바꿨으니 `ENGINE`을 `"2026-10-22c"`로 올린다(전원 자동 재계산).
- 유지 도술(조건 없음, 1회량 = 공격력 배수): 생명의 흐름 0.60(12%×5, 쿨 15), 생명의 축복 0.35(쿨 20), 방패 밀기 0.70(쿨 15), 방패 충격파 0.35(쿨 20), 강인한 의지 0.35(쿨 30).
- 조건부 유지(표식을 거는 도술이 트리에 있을 때만 셈, `도술_정보.md` 5-2): 회전 난격·날카로운 얼음창 0.10(기세), 연속 찌르기 0.15(기세), 찌르기 0.10(낙인), 휘둘러 내려치기 0.15(낙인), 휘둘러치기 0.15(질풍), 먹 베기 0.10(수호), 도약 찌르기 0.15(수호). 표식을 거는 도술: 기세 = 내려치기·올려치기·대검 찍기, 낙인 = 내려찍기·약점 베기, 질풍 = 찌르기·연속 찌르기, 수호 = 방패 치기·방패 내려찍기.
- 등급 규칙: 딜 = 유지 0개 중 딜 1위 / 믹스 = 유지 1개 중 딜 카드 대비 −5% 안에서 유지력 최대(없으면 유지 1개 중 딜 1위) / 생존 = 유지 2개 이상 중 −10% 안에서 유지력 최대(없으면 2개 이상 중 딜 1위).
- 힐은 사용 순서 맨 앞(지금 규칙 그대로).
- 사냥터 키와 이름(1단계는 코드 상수, `d:grounds` 표는 2단계): `wild` 황무지, `well` 우물동굴 215k, `mine` 음산한 폐광 260k, `secret` 비경(3종 이름 받기 전까지 칩 하나, 몰이 모델), `boss` 보스.
- 커뮤니티 덱: 10/21 패치 이후 글만 = `created_at >= 1792508400`(2026-10-21 00:00 KST). 순서 = 안 배운 도술 없는 덱 먼저 → `likes − 2 × dislikes` 큰 순.
- 저장 서버 `pick`: `{a:"pick", nick, pin, prefStyle?, mybuilds?}` → PIN 확인 후 data의 `prefStyle`·`mybuilds`만 바꿈, `updatedAt` 그대로, dispatch 안 함, 크기 한도 45,000자.
- 사이트 패치노트는 개인 기준 문구 없이 버전 +0.1(지금 4.0 → 4.1).
- 배포(Vercel `npx vercel deploy --prod --yes`, `dokkaebi-dosa` push)는 밖으로 나가는 작업이라 실행 직전에 사용자에게 확인받는다.

### 이 계획에서 정한 것 (설계 14장 "만드는 사람이 정할 것" + 빈칸)

- 덱 광역/단일 판정: 8칸 중 범위 도술(`targets.json` 대상 2 이상)이 **4개 이상이면 광역**, 아니면 단일.
- 덱 사냥터 키워드(제목+본문, 대소문자 무시): `wild` 황무지 / `well` 우물, 215k / `mine` 폐광, 260k / `secret` 비경 / `boss` 보스, 레이드, 필보. 여러 개 맞으면 모두에 넣는다.
- 덱은 모든 페이지(최대 30페이지, 지금 22페이지·316개)를 받는다.
- 카드 하나의 커뮤니티 목록은 최대 10개(1개 표시 + 접힌 9개), 사냥터 미지정 목록은 최대 30개.
- 덱 상세는 결과의 `decks`에 한 번만 두고 카드는 `{id, pct}`로 가리킨다(결과 크기 줄이기).
- **정기 재계산 기준은 11시간**: 설계는 "12시간보다 오래됨"이지만, 정기 실행(9시·21시)의 간격이 정확히 12시간이고 결과 기록 시각이 실행 시작보다 늦어서 12시간으로 하면 한 번 걸러 건너뛴다. 의도(하루 두 번 모두 재계산)대로 되도록 11시간.
- 보스 생존·믹스 계산 1위는 4단계라서 1단계에서는 `calc: null`(커뮤니티 빌드만 표시).
- 예전 결과(`grounds` 없음)는 예전 추천 트리 화면을 그대로 보여 준다(ENGINE을 올려서 곧 다시 계산됨).
- 예시 결과(`tools/example_recs.json`)는 개인 정보 없는 가상 프로필(`tools/example_profile.json`)로 다시 만든다.

## Review Focus

1. **정기 재계산 경계**: 9시 실행이 9시 20분에 결과를 쓰고 21시 실행이 돌면, 그 프로필은 다시 계산돼야 한다 → Task 5의 `stale` 점검(11시간 30분 지난 결과 = 다시 계산).
2. **광역 도술이 모자란 프로필**: 몰이 탐색이 `None`이면 광역 카드 계산 1위가 없다. 분석이 죽지 않고 `calc: null`을 내고, 사이트는 "계산할 수 없음"을 보여야 한다 → Task 5의 저격·파멸만 배운 프로필 점검, Task 8 화면 확인 항목.
3. **이상한 커뮤니티 덱**: 궁극기가 없거나, 칸이 비었거나, 모르는 도술 이름이 있는 덱 → 분류에서 조용히 빠지고 분석은 계속 → Task 4 점검.
4. **등록 안 된 닉네임의 pick**: 서버는 새 프로필을 만들지 않고 `none`을 돌려줘야 한다. 사이트는 로그인 전이면 요청을 보내지 않고 화면·임시 저장에만 둔다 → Task 6 점검, Task 9 확인 항목.
5. **"215k~260k" 같은 덱**: 여러 사냥터에 동시에 들어가야 한다 → Task 4 점검.

---

### Task 1: 유지력 표(`sim/sustain.py`)와 점검 한 섹션만 돌리기

**Files:**
- Create: `sim/sustain.py`
- Modify: `tools/check.py` (섹션 추가, `--only` 옵션)

**Interfaces:**
- Produces:
  - `UNCOND: dict[str, float]` 조건 없는 유지 도술 → 1회량(공격력 배수), `COND: dict[str, tuple[str, float]]` 받는 도술 → (표식, 1회량), `MARK_SRC: dict[str, set[str]]` 표식 → 거는 도술
  - `active(order: list[str]) -> list[str]` 트리에서 유지력이 실제로 나오는 도술(순서 유지)
  - `count(order) -> int` = `len(active(order))`
  - `rate(order, casts: dict[str, int], seconds: float) -> float` 초당 '공격력의 N%'(퍼센트 숫자)
  - `tools/check.py --only <섹션 이름>`: 그 섹션만 실행(예: `--only 유지력`)

- [ ] **Step 1: 점검 쓰기** — `tools/check.py`에 `sustain_checks()`와 `--only` 처리 추가, 섹션 목록에 `("유지력", sustain_checks)`.

```python
def sustain_checks():
    ok(SU.count(["생명의 흐름", "방패 밀기", "사격"]) == 2, "유지력: 흐름+방패 밀기가 2개로 안 셈")
    ok(SU.count(["회전 난격", "사격"]) == 0, "유지력: 기세 없이 회전 난격 회복을 셈")
    ok(SU.count(["회전 난격", "대검 찍기"]) == 1, "유지력: 대검 찍기(기세)와 회전 난격을 1개로 안 셈")
    ok(SU.count(["찌르기", "휘둘러치기"]) == 1, "유지력: 찌르기(질풍)→휘둘러치기 보호막을 안 셈")
    ok(SU.active(["방패 밀기", "생명의 흐름"]) == ["방패 밀기", "생명의 흐름"], "유지력: 순서가 바뀜")
    ok(abs(SU.rate(["생명의 흐름"], {"생명의 흐름": 20}, 300) - 4.0) < 1e-9, "유지력: 흐름 20회/300초가 초당 4%가 아님")
    ok(SU.rate(["회전 난격"], {"회전 난격": 30}, 300) == 0, "유지력: 표식 없는 조건부 회복이 들어감")
    for n in list(SU.UNCOND) + list(SU.COND) + [x for v in SU.MARK_SRC.values() for x in v]:
        ok(n in NAMES, f"유지력 표: 없는 도술 이름 '{n}'")
```

- [ ] **Step 2: 실패 확인** — Run: `python tools/check.py --only 유지력` / Expected: `ModuleNotFoundError: sustain` 또는 실패 메시지

- [ ] **Step 3: `sim/sustain.py` 구현** — 값은 Global Constraints 표 그대로. `rate`는 `active(order)`에 든 도술만 `casts × 1회량` 합 ÷ 초 × 100.

- [ ] **Step 4: 통과 확인** — Run: `python tools/check.py --only 유지력` / Expected: `유지력: 통과`, 종료 코드 0

- [ ] **Step 5: 커밋** — `git add sim/sustain.py tools/check.py && git commit -m "유지력 표: 조건 없는·조건부 회복·보호막, 초당 공격력 %"`

---

### Task 2: 시전 횟수 세기(몰이·필드)

**Files:**
- Modify: `sim/mob.py` (`sim`에 `cnt` 인자, `casts` 함수), `sim/timeline.py` (`Sim.casts`), `sim/field.py` (`casts` 함수)
- Test: `tools/check.py` (`model_checks`에 추가)

**Interfaces:**
- Produces:
  - `M.casts(order: list[str]) -> dict[str, int]` — 5마리, `flat`, Kc 20, 300초 한 번 돌린 시전 횟수(궁극기 포함)
  - `S.Sim.casts: dict[str, int]` — `cast()`마다 `s["n"]` 하나씩
  - `F.casts(names: list[str], order: list[str]) -> dict[str, int]` — `HUNT_P[0]`, `T`초, 연계 켬
  - 공통 상수 `SEC = 300`(두 함수 모두 300초 기준. `SU.rate(..., 300)`에 그대로 넘긴다)

- [ ] **Step 1: 점검 쓰기** — `model_checks` 끝에:

```python
    setup(p)
    mo_h = ["생명의 흐름"] + [x for x in mo if x not in F.HEALS][:7]
    c = M.casts(mo_h)
    ok(10 <= c.get("생명의 흐름", 0) <= 20, f"몰이 시전 횟수: 생명의 흐름(쿨 15초) 300초 {c.get('생명의 흐름')}회")
    ok(abs(M.w(mo) - base["몰이"]) < 1e-9, "몰이: 시전 횟수 세기 뒤 점수가 달라짐")
    c2 = F.casts(rc + ["생명의 흐름"], ["생명의 흐름"] + ro)
    ok(10 <= c2.get("생명의 흐름", 0) <= 20, f"필드 시전 횟수: 생명의 흐름 300초 {c2.get('생명의 흐름')}회")
    ok(abs(F.kills(rc, ro, 0.3) - base["필드"]) < 1e-9, "필드: 시전 횟수 세기 뒤 점수가 달라짐")
```

  (필드 모델은 칸 수를 검사하지 않아서 9개 이름도 그대로 계산된다. 힐은 `_prep`이 피해 0 시전으로 붙인다.)

- [ ] **Step 2: 실패 확인** — Run: `python tools/check.py --only "계산 모델"` / Expected: `AttributeError: ... 'casts'`

- [ ] **Step 3: 구현** — `mob.sim(order, n, T=300, cast="flat", Kc=20, dot_rage=True, cnt=None)`: 시전할 때(`k` 확정 후) `cnt[k] = cnt.get(k, 0) + 1`. 반환값은 그대로. `Sim.__init__`에 `self.casts = {}`, `cast()` 첫 줄에서 셈. `F.casts`는 `kills`와 같은 준비(`_prep`, 정렬, `S.SYN = True`) 후 `S.Sim(...)`을 직접 만들어 `run()` 하고 `.casts` 반환, 끝나면 전역(`AMP_HIT`)을 `kills`처럼 둔다.

- [ ] **Step 4: 통과 확인** — Run: `python tools/check.py --quick` / Expected: 모든 섹션 `통과`(실측 재현 포함, 점수 변화 없음)

- [ ] **Step 5: 커밋** — `git commit -am "몰이·필드 계산에서 도술 시전 횟수 세기(유지력 계산용)"`

---

### Task 3: 등급별 계산 1위 고르기(`sim/tiers.py`)

**Files:**
- Create: `sim/tiers.py`
- Test: `tools/check.py` (`tier_checks`, 섹션 "등급")

**Interfaces:**
- Consumes: `SU.active`, `SU.count`, `SU.UNCOND`
- Produces:
  - 후보 dict `Cand = {"score": float, "order": list[str], "ult": str, "susN": int, "sus": float, **extra}`(extra는 `kind`·`tr` 등 호출자가 붙임)
  - `add_sustain(order, ult, skill, score: Callable[[list], float], ok: Callable[[list], bool]) -> tuple[float, list] | None` — 기존 힐은 맨 앞 유지, `skill`이 힐이면 기존 힐 바로 뒤에, 아니면 바꾼 칸 자리에. 궁극기·영혼 소용돌이·이미 든 유지 도술(`SU.active`)은 빼지 않는다. 가장 점수 높은 것.
  - `expand(seeds: list[Cand], owned: set, score, ok, make: Callable[[float, list, str], Cand]) -> list[Cand]` — seeds + 유지 0개 1위에 유지 도술 1개씩 + 유지 1개 상위 5개에 1개 더 + 유지 2개 상위 5개에 1개 더(설계 9장 "힐 2 + 보호막 포함"). 같은 순서는 한 번만.
  - `pick_tiers(cands: list[Cand]) -> dict[str, Cand | None]` 키 `"딜"`·`"믹스"`·`"생존"`. 기준 점수 = 딜 카드 점수(딜 후보가 없으면 전체 최고 점수). 고른 후보에 `dmgPct = (score / 기준 − 1) × 100` 붙임.
  - 상수 `WIN = {"믹스": 0.95, "생존": 0.90}`

- [ ] **Step 1: 점검 쓰기** — 가짜 점수(도술마다 정한 값의 합)로:

```python
def tier_checks():
    c = lambda s, n, v: {"score": s, "order": [f"x{s}"], "ult": "u", "susN": n, "sus": v}
    t = TI.pick_tiers([c(100, 0, 0), c(97, 1, 2), c(96, 1, 5), c(90, 1, 9), c(91, 2, 6), c(89, 3, 12)])
    ok(t["딜"]["score"] == 100, "등급: 딜이 유지 0개 1위가 아님")
    ok(t["믹스"]["sus"] == 5, "등급: 믹스가 −5% 안 유지력 최대가 아님")
    ok(t["생존"]["sus"] == 6, "등급: 생존이 −10% 안 유지력 최대가 아님(89는 한도 밖)")
    ok(abs(t["믹스"]["dmgPct"] + 4) < 1e-9, "등급: 딜 대비 %가 틀림")
    t2 = TI.pick_tiers([c(100, 0, 0), c(80, 1, 3), c(70, 1, 9)])
    ok(t2["믹스"]["score"] == 80 and t2["생존"] is None, "등급: 한도 안 후보가 없을 때 유지 1개 중 딜 1위가 아님")
    t3 = TI.pick_tiers([c(90, 1, 3)])
    ok(t3["딜"] is None and t3["믹스"]["dmgPct"] == 0, "등급: 딜 후보가 없을 때 기준이 전체 1위가 아님")
    V = {"a": 10, "b": 8, "c": 6, "생명의 흐름": 0, "방패 밀기": 3, "u": 0}
    sc = lambda o: sum(V[x] for x in o)
    r = TI.add_sustain(["a", "b", "c", "u"], "u", "생명의 흐름", sc, lambda o: True)
    ok(r and r[1] == ["생명의 흐름", "a", "b", "u"], f"등급: 힐이 맨 앞·가장 약한 칸 대신이 아님 {r}")
    r = TI.add_sustain(["생명의 흐름", "a", "b", "c", "u"], "u", "방패 밀기", sc, lambda o: True)
    ok(r and r[1] == ["생명의 흐름", "a", "b", "방패 밀기", "u"], f"등급: 보호막이 바꾼 칸 자리에 안 들어감 {r}")
    ok(TI.add_sustain(["a", "u"], "u", "방패 밀기", sc, lambda o: False) is None, "등급: 규칙에 안 맞는 배치를 돌려줌")
```

- [ ] **Step 2: 실패 확인** — Run: `python tools/check.py --only 등급` / Expected: `ModuleNotFoundError: tiers`

- [ ] **Step 3: `sim/tiers.py` 구현** — 위 시그니처대로. 같은 유지력이면 점수 큰 것.

- [ ] **Step 4: 통과 확인** — Run: `python tools/check.py --only 등급` / Expected: `등급: 통과`

- [ ] **Step 5: 커밋** — `git commit -m "등급별 계산 1위: 유지 도술 개수·딜 손해 한도 안 유지력 최대"` (새 파일 add 포함)

---

### Task 4: 커뮤니티 덱 분류·순서(`sim/decks.py`)

**Files:**
- Create: `sim/decks.py`
- Test: `tools/check.py` (`deck_checks`, 섹션 "커뮤니티 덱")

**Interfaces:**
- Consumes: `SU.count`, `targets.json`(대상 수), 도술 이름 집합(`timeline.BY`)
- Produces:
  - 상수 `GROUNDS = {"wild": "황무지", "well": "우물동굴 215k", "mine": "음산한 폐광 260k", "secret": "비경", "boss": "보스"}`(순서 = 칩 순서), `KEYWORDS`, `PATCH_AT = 1792508400`, `PER_CARD = 10`, `UNASSIGNED = 30`
  - `parse(bd) -> dict | None` — `{id, name, author, likes, dislikes, at, body, slots, order, ult}`. `order`는 `analyze.community()`와 같은 방식(궁극기를 `ult_at` 위치에 넣음). 궁극기 없음·칸 비어 있음·모르는 도술 이름이 있으면 `None`.
  - `grounds_of(d) -> list[str]`, `style_of(d) -> "광역" | "단일"`(범위 도술 4개 이상 = 광역), `tier_of(d) -> "딜" | "믹스" | "생존"`(`SU.count(order)` 0 / 1 / 2 이상), `video(d) -> str | None`(본문 첫 youtube.com·youtu.be·chzzk.naver.com·sooplive·afreecatv 링크)
  - `rank(ds, owned) -> list` — 안 배운 도술 0개 먼저, 그다음 `likes − 2 × dislikes` 큰 순
  - `classify(raw: list[dict], owned: set) -> tuple[dict, list, dict]` — `(placed, unassigned, info)`. `placed[g][style][tier] = [id, ...]`(보스는 style 키 `"보스"`, 최대 `PER_CARD`), `unassigned = [id, ...]`(최대 `UNASSIGNED`), `info[id] = {name, author, likes, video, slots, order, ult, missing}`. 패치 전 덱은 버린다.

- [ ] **Step 1: 점검 쓰기** — 가짜 덱 생성 함수 `deck(i, name, body, slots, ult, at=PATCH_AT + 1, likes=0)`(slots·order는 이름 dict 목록)로:
  - 이름 "215k~260k 몰이" → `grounds_of == ["well", "mine"]`
  - 이름·본문에 사냥터 없음 → `unassigned`에만 있고 `placed` 어디에도 없음
  - `at = PATCH_AT - 1` → 어디에도 없음
  - 궁극기 없는 덱, 칸에 모르는 이름("없는도술")이 있는 덱 → `parse(...) is None`, `classify`가 예외 없이 건너뜀
  - 범위 도술 4개(예: 화염구·낙뢰·번개 폭풍·연쇄 번개) + 단일 4개 → `"광역"`, 범위 3개 → `"단일"`
  - 생명의 흐름 + 방패 밀기 → `"생존"`, 흐름만 → `"믹스"`
  - 같은 칸의 덱 두 개: 추천 50(안 배운 도술 1개) vs 추천 10(다 배움) → 추천 10이 먼저; 둘 다 배움일 때 추천 50·비추천 30(=−10) vs 추천 0 → 추천 0이 먼저
  - 본문 "영상 https://www.youtube.com/watch?v=abc 참고" → `video == "https://www.youtube.com/watch?v=abc"`
  - "보스" 덱 → `placed["boss"]["보스"][tier]`에 들어감

- [ ] **Step 2: 실패 확인** — Run: `python tools/check.py --only "커뮤니티 덱"` / Expected: `ModuleNotFoundError: decks`

- [ ] **Step 3: `sim/decks.py` 구현** — 키워드 비교는 `(name + " " + body).lower()`. `info`의 `missing`은 `owned`에 없는 칸 도술.

- [ ] **Step 4: 통과 확인** — Run: `python tools/check.py --only "커뮤니티 덱"` / Expected: `커뮤니티 덱: 통과`

- [ ] **Step 5: 커밋** — `git commit -m "커뮤니티 덱 분류: 사냥터 키워드·광역/단일·생존/믹스/딜, 패치 이후·바로 쓸 수 있는 순"`

---

### Task 5: 분석 결과에 `grounds` 넣기 + 정기 재계산

**Files:**
- Modify: `analyze.py`
- Test: `tools/check.py` (`result_checks` 확장)

**Interfaces:**
- Consumes: Task 1~4의 모든 함수, `M.casts`, `F.casts`
- Produces (결과 JSON, 사이트가 읽음):

```text
result.grounds = { "<g>": { "name": str, "styles": { "광역"|"단일"|"보스": { "딜"|"믹스"|"생존": {
    "calc": null | { "label": str, "slots": [8], "order": [...], "ult": str, "score": float,
                     "dmgPct": float, "sus": float, "susN": int, "sustain": [유지 도술 이름], "kind": "mob"|"field"|"boss" },
    "comm": [ { "id": int, "pct": float|null } ] } } } } }
result.decks = { "<id>": { "name", "author", "likes", "video", "slots", "order", "ult", "missing" } }
result.unassigned = [ { "id": int, "style": "광역"|"단일", "tier": str, "pct": float|null } ]
```

  - `analyze.REFRESH_H = 11`, `stale(x, now_ms=None)`: 지금 조건 + `resultAt`이 11시간보다 오래됨(배운 도술 없는 프로필은 계속 제외). `resultAt`이 없거나 빈 값이면 이 조건은 보지 않는다(기존 점검 "지금 방식으로 계산한 결과를 다시 계산하려 함"이 그대로 통과해야 함)
  - `mob_search(owned, heals, cap=None)` / `_mob_one(..., cap=None)`: `cap`이 있으면 처음 고르기와 칸 바꾸기에서 `SU.count(order_of(t)) > cap`인 배치를 건너뜀
  - 새 탐색 작업 `("mob0",)` → `mob_search(owned, 0, cap=0)`, 결과 `(score, order, ult)` 또는 `None`
  - `load_builds()` → 패치 이후·칸·궁극기 있는 덱 전부(최대 30페이지). 기존 `comm_` 트리는 그중 추천 수 상위 5개로 그대로.
  - `build_grounds(R, owned) -> dict` (결과의 세 키를 담은 dict)

- [ ] **Step 1: 점검 쓰기** — `result_checks`에 추가:

```python
    g = r.get("grounds") or {}
    ok(list(g) == ["wild", "well", "mine", "secret", "boss"], f"사냥터 순서·키가 다름 {list(g)}")
    for gk, gv in g.items():
        for stn, tiers in gv["styles"].items():
            ok(set(tiers) == {"딜", "믹스", "생존"}, f"{gk}/{stn}: 등급 3개가 아님")
            for tn, card in tiers.items():
                cl = card["calc"]
                if cl:
                    tree_checks({"id": f"{gk}_{tn}", **cl, "stat": ""}, set(p["owned"]), "등급 카드")
                    want = {"딜": cl["susN"] == 0, "믹스": cl["susN"] == 1, "생존": cl["susN"] >= 2}[tn]
                    ok(want, f"{gk}/{stn}/{tn}: 유지 도술 {cl['susN']}개")
                    hs = [x for x in cl["order"] if x in F.HEALS]
                    ok(cl["order"][:len(hs)] == hs, f"{gk}/{stn}/{tn}: 힐이 맨 앞이 아님")
                for e in card["comm"]:
                    ok(str(e["id"]) in r["decks"], f"{gk}/{stn}/{tn}: decks에 없는 덱 {e['id']}")
    ok(g["boss"]["styles"].keys() == {"보스"}, "보스는 광역/단일 없이 '보스' 하나여야 함")
    ok(g["well"]["styles"]["광역"]["딜"]["calc"] is not None, "작은 프로필: 광역 딜 카드 계산 1위가 없음")
    # 정기 재계산: 11시간 넘은 결과는 다시, 1시간 된 결과는 그대로
    now = 2_000_000_000_000
    fresh = {"updatedAt": "1", "resultFor": "1", "result": r, "data": d, "resultAt": str(now - 3600_000)}
    ok(not A.stale(fresh, now), "1시간 전 결과를 다시 계산하려 함")
    ok(A.stale(dict(fresh, resultAt=str(now - int(11.5 * 3600_000))), now), "11시간 30분 지난 결과를 다시 계산하지 않음(정기 실행 간격 12시간)")
    ok(not A.stale(dict(fresh, data={}, resultAt="0"), now), "비운 프로필을 정기 재계산하려 함")
    # 광역 도술이 모자란 프로필: 죽지 않고 광역 계산 1위 없음
    r2 = A.analyze({"levels": {"저격": 5}, "owned": {n: {} for n in ALL if STYLE_OF[n] == "저격"}})
    ok(not [n for n in r2["notes"] if "오류" in n], f"저격만 배운 프로필 분석 오류 {r2['notes']}")
    ok(r2["grounds"]["well"]["styles"]["광역"]["딜"]["calc"] is None, "광역 도술이 없는데 광역 카드 계산 1위가 있음")
```

  (`tree_checks`는 `slots` 8칸·하단 5칸 규칙을 본다. 칸 수가 8이 아닌 프로필은 이 점검에 넣지 않는다.)

- [ ] **Step 2: 실패 확인** — Run: `python tools/check.py --only "결과 형식"` / Expected: `사냥터 순서·키가 다름 []` 등 실패

- [ ] **Step 3: 구현** — 순서대로:
  1. `mob_search`/`_mob_one`에 `cap`, `_job`에 `"mob0"`, `analyze()`의 `jobs`에 `("mob0",)`, `run_jobs`의 `weight`에 `"mob0": 1`.
  2. `build_grounds(R, owned)`:
     - 광역 씨앗: `R[("mob",)]`의 세 결과 + `R[("mob0",)]` → `Cand(kind="mob")`. 점수 `M.w`, 규칙 검사 = 궁극기 스타일 3개(`_mob_one`과 같은 식) + `M.valid_order`. 유지력 = `SU.rate(o, M.casts(o), 300)`.
     - 단일 씨앗: `pure`·`single`(rng의 `single_top`)·`pureh`·`singleh`(`rh`)·`jhunt`·`jhunt_h`·`hunt_<스타일>`의 (점수, 순서, 궁극기, 이동 시간: 원거리 0.3 / 절명 0.7 / `hunt_st`는 결과의 `tr_`). 점수 `F.kills(arrange(o, u), o, tr)`, 규칙 검사 = `arrange`가 실패하지 않음, 유지력 = `SU.rate(o, F.casts(arrange(o, u), o), 300)`.
     - 각 스타일: `TI.expand` → `TI.pick_tiers`. 카드 `calc`에 `slots = arrange(order, ult)`, `sustain = SU.active(order)`, `label = f"궁극기 {ult} · " + ("·".join(sustain) or "유지 도술 없음")`.
     - 보스: 딜 = `boss`·`boss_<스타일>` 중 점수 1위(`susN`은 `SU.count`), 믹스·생존 `calc: None`.
     - 황무지·우물·폐광·비경은 같은 광역/단일 카드(계산 1위는 사냥터마다 같아도 됨, 설계 9장).
     - 커뮤니티: `DK.classify(BUILDS, owned)` → 덱 점수는 카드 종류의 모델로 한 번씩만(캐시 키 `(id, kind)`): 광역 `M.w`(몰이 도술만, `community()`와 같게), 단일 `F.kills(known, fo, 0.7 if 근접 4개 이상 else 0.3)`, 보스 `F.boss_score`. `pct = (덱 점수 / 카드 calc 점수 − 1) × 100`, calc 없으면 `None`. 미지정 덱은 자기 스타일의 딜 카드(우물 기준) 대비.
  3. `analyze()`에서 `mark_best` 전에 `res.update(build_grounds(R, owned))`(예외면 `notes`에 "사냥터 추천 계산 실패(예외 이름)"를 남기고 `grounds` 없이 진행), `progress(53, "사냥터별 추천")`.
  4. `load_builds()` 전 페이지 + 패치 이후만, `comm_` 트리는 `BUILDS` 추천 수 상위 5개.
  5. `REFRESH_H`, `stale(x, now_ms=None)`(`now_ms` 기본 `time.time() * 1000`), `ENGINE = "2026-10-22c"`.

- [ ] **Step 4: 통과 확인** — Run: `python tools/check.py` (전체, 수 분) / Expected: 모든 섹션 `통과`

- [ ] **Step 5: 커밋** — `git commit -am "분석 결과에 사냥터별 생존·믹스·딜 카드(grounds)와 커뮤니티 덱 분류, 정기 재계산(11시간), 계산 버전 2026-10-22c"`

---

### Task 6: 저장 서버 `pick`(재계산 없는 저장)

**Files:**
- Create: `server/lib/pick.js`, `server/test/pick.test.js`
- Modify: `server/api/dosa.js` (머리 주석 목록, `handlePost`)

**⚠ 실행 전 사용자 확인:** 팀 규칙상 테스트 장치가 없는 곳에 새로 만들기 전에 묻는다. 제안: 패키지 설치 없이 Node 내장 `node --test`. 사용자가 거절하면 Step 1·2·4를 건너뛰고 Step 6의 curl 확인만 한다.

**Interfaces:**
- Produces:
  - `applyPick(data: object, b: object, maxData: number) -> {ok: true, data} | {ok: false, err: "input" | "size"}` — `prefStyle`은 `"광역"`·`"단일"`만, `mybuilds`는 배열이 아닌 객체만, 둘 다 없으면 `input`. 원본 `data`는 바꾸지 않는다.
  - POST `{a:"pick", nick, pin, prefStyle?, mybuilds?}` → `{ok: true}` / `{ok: false, err: "input"|"none"|"pin"|"size"}`. 프로필이 없으면 만들지 않는다(`none`). `updatedAt`·`resultFor`는 그대로, `dispatch` 안 부름.

- [ ] **Step 1: 테스트 쓰기** — `server/test/pick.test.js`(`node:test`, `node:assert/strict`):
  - `{levels:{a:1}}` + `{prefStyle:"단일"}` → `data.prefStyle === "단일"`, `levels` 그대로, 원본 객체 안 바뀜
  - `{prefStyle:"전부"}` → `err "input"`; `{mybuilds:[1]}` → `input`; `{}` → `input`
  - `{mybuilds:{well:{tier:"딜"}}}` → `data.mybuilds.well.tier === "딜"`
  - `maxData = 50`에 큰 `mybuilds` → `err "size"`

- [ ] **Step 2: 실패 확인** — Run: `node --test server/test/` / Expected: `Cannot find module ... lib/pick.js`

- [ ] **Step 3: 구현** — `server/lib/pick.js`(ESM export). `dosa.js`의 `handlePost`에 `b.a === "pick"` 분기: `save`와 같은 닉네임·PIN 검사 → `p:` 읽기(없으면 `none`) → `pinHash` 확인 → `applyPick(prof.data || {}, b, MAX_DATA)` → `prof.data = r.data` → `putProfile(prof)` → `{ok: true}`. 머리 주석에 `POST {a:"pick", ...}` 한 줄.

- [ ] **Step 4: 통과 확인** — Run: `node --test server/test/` / Expected: 테스트 전부 pass

- [ ] **Step 5: 커밋** — `git add server/lib server/test server/api/dosa.js && git commit -m "저장 서버: pick(내 빌드·광역/단일 즉시 저장, 재계산 없음)"`

- [ ] **Step 6: 배포와 확인 (사용자 확인 후)** — `cd server && npx vercel deploy --prod --yes`(로그인이 안 돼 있으면 사용자가 `! npx vercel login`). 확인: 테스트 닉네임(`테스트`, 길드원 현황에서 숨겨진 이름)으로
  - `curl -s -X POST <API> -d '{"a":"pick","nick":"없는닉네임xyz","pin":"0000","prefStyle":"단일"}'` → `{"ok":false,"err":"none"}`
  - `테스트`로 pick → `ok:true`, 이어서 `?a=status&nick=테스트`의 `updatedAt`이 pick 전과 같음

---

### Task 7: 도술 아이콘 복사 도구

**Files:**
- Create: `tools/mkicons.py`, `site/icons.json`(생성물, 커밋)

(일회성 도구 + 생성물 → TDD 제외. 결과 개수로 확인.)

**Interfaces:**
- Produces: `site/icons.json` = `{도술 이름: "파일이름.webp"}`(103개, 사슬 묶기 없음). 사이트 저장소 `dokkaebi-dosa/icons/*.webp`.
- 사용법: `python tools/mkicons.py <아이콘 폴더> <사이트 저장소 폴더>` — `data/skills.json`의 `i` 경로 파일명의 확장자를 `.webp`로 바꿔 찾고, 있으면 복사하고 표에 넣는다. 없는 도술 이름을 출력.

- [ ] **Step 1: 구현**
- [ ] **Step 2: 실행** — Run: `python tools/mkicons.py ../../icons ../dokkaebi-dosa` / Expected: `103개 복사 · 없음: 사슬 묶기`, `site/icons.json` 103줄 항목
- [ ] **Step 3: 커밋** — `git add tools/mkicons.py site/icons.json && git commit -m "도술 아이콘 표와 복사 도구"` (`dokkaebi-dosa` 쪽 커밋은 Task 9에서 사이트와 함께)

---

### Task 8: 사이트 탭 2개 + [추천 빌드] 탭

**Files:**
- Create: `site/builds.js`, `site/builds.css`
- Modify: `tools/mksite.py`

(UI → TDD 제외. 확인은 `node --check`와 브라우저.)

**Interfaces:**
- Consumes: 결과 JSON(Task 5), `site/icons.json`(Task 7), `pick`(Task 6), mksite가 만든 전역 `state`·`auth`·`api`·`PIN`·`el`·`$`·`setStatus`·`saveDraft`·`RECS`·`myRes`
- Produces (Task 9가 씀): `ICONS`(mksite가 `icons.json`을 `const ICONS = {...};`로 넣음), `iconRow(order: string[], ult: string): HTMLElement`, `sendPick(): void`(로그인 전이면 요청 없이 `saveDraft()` + 안내 문구, 아니면 `{a:"pick", nick, pin, prefStyle, mybuilds}`), `renderBuilds(): void`, `TIER_ORDER = ["생존", "믹스", "딜"]`

- [ ] **Step 1: mksite 고치기**
  - `normalize`에 `s.prefStyle = s.prefStyle === "단일" ? "단일" : "광역"; s.mybuilds = s.mybuilds || {};` 추가(rep).
  - `.mtabs`를 모든 화면 너비에서 보이게: 라벨 `[내 수첩]`(`data-mt="skills"`) `[추천 빌드]`(`data-mt="recs"`). `body[data-mt="recs"] .col-l` / `body[data-mt="skills"] .col-r` 숨김, PC(1280px 이상)에서 `.cols`를 한 칸(`grid-template-columns:minmax(0,1fr)`)으로.
  - `col-r`에 `<section id="sec-builds" hidden><h2>추천 빌드</h2><p class="hint" id="bdBasis"></p><div id="bd"></div></section>` 추가.
  - `renderRight`: `RECS.grounds`가 있으면 `sec-recs` 숨기고 `sec-builds` 보이며 `renderBuilds()`, 없으면 지금 화면.
  - `site/builds.css`는 `</style>` 앞에, `ICONS` + `site/builds.js`는 휴대폰 탭 코드(`const LSM = ...`) 앞에 넣는다. 아이콘 경로는 `icons/<파일>`.
- [ ] **Step 2: `site/builds.js`·`builds.css`** — 설계 7-1 그대로:
  - 사냥터 칩(결과 `grounds` 키 순서, 마지막 본 사냥터를 `localStorage` `dosa-notebook-site-ground`에 기억, try/catch)
  - `[광역 | 단일]`(보스면 숨김). 바꾸면 `state.prefStyle` 변경 + `sendPick()`
  - 카드 3장(생존·믹스·딜) PC 가로, 좁으면 세로. 머리: 등급 이름, '내 빌드' 배지(이 사냥터 `mybuilds`의 `tier`·`style`·`order`가 이 카드 후보와 같을 때)
  - 후보 ① 계산 1위: `label`, 수치 한 줄(딜 카드면 "딜 기준", 아니면 `딜 카드 대비 −3%` 식, `유지력 초당 공격력의 N%`), 아이콘 행, [이걸로]. `calc`가 `null`이면 "계산할 수 없음(배운 도술이 모자람)" 또는 보스면 "보스 생존·믹스 계산은 준비 중"
  - 후보 ② 커뮤니티 1개: '커뮤니티' 표시, 작성자·추천 수·영상 링크(새 창, `rel="noopener"`), `계산 1위 대비 ±N%`, `안 배운 도술 N개`, 아이콘 행, [이걸로]. 없으면 "이 조건의 커뮤니티 빌드 없음"
  - "커뮤니티 빌드 N개 더 ▾" `<details>`
  - 맨 아래 '사냥터 미지정 커뮤니티 빌드' `<details>`(덱마다 광역/단일·등급 표시)
  - 아이콘 행: 사용 순서대로 32px, 왼쪽 위 번호, 궁극기 금색 테두리, 힐 초록 테두리, `title` = 도술 이름. 아이콘 없는 도술은 이름 글자 칸
  - [이걸로] → `state.mybuilds[g] = {tier, style, from: "calc"|"comm", commId?, order, ult, slots, pickedAt: Date.now(), result: 이전 result 유지}` → `sendPick()` → 다시 그림
  - 색은 기존 CSS 변수(`--accent`, `--ok`, `--warn`, `--line`, `--panel`)만 써서 밝은/어두운 테마 둘 다
- [ ] **Step 3: 만들고 검사** — 저장 서버 URL은 비공개 기록 폴더 `repo/secret`에 있다. Run: `python tools/mksite.py site/base.html ../dokkaebi-dosa/index.html "<저장 서버 URL>"` → `ok <크기>`; 이어서 `index.html`의 `<script>…</script>` 내용을 스크래치 폴더의 `site.js`로 뽑아(`re.findall(r"<script>(.*?)</script>", h, re.S)`) `node --check <그 파일>` / Expected: 오류 없음
- [ ] **Step 4: 커밋** — `git add site/builds.js site/builds.css tools/mksite.py && git commit -m "사이트: 탭 2개(내 수첩/추천 빌드), 사냥터별 생존·믹스·딜 카드와 아이콘"`

---

### Task 9: [내 수첩]의 내 빌드 목록 + 예시 결과 + 배포

**Files:**
- Modify: `site/builds.js`, `site/builds.css`, `tools/mksite.py`
- Create: `tools/example_profile.json`(가상 프로필, 개인 정보 없음)
- Modify: `tools/example_recs.json`(다시 만듦), `../dokkaebi-dosa/patchnotes.json`, `../dokkaebi-dosa/index.html`, `../dokkaebi-dosa/icons/`

**Interfaces:**
- Consumes: `iconRow`, `sendPick`, `TIER_ORDER`(Task 8), `decks.GROUNDS` 이름(결과 `grounds[g].name`)

- [ ] **Step 1: 내 빌드 목록** — mksite로 `col-l`의 `sec-skills` 다음에 `<section id="sec-mybuilds"><h2>내 빌드</h2><div id="mb"></div></section>`. `renderMyBuilds()`: 사냥터별로 고른 빌드(아이콘 행 + "계산 1위"/"커뮤니티: 덱 이름" + 등급·광역/단일). 옆에 "돌려 본 결과": 물약(선택: 안 적음/썼음/안 씀), 분당 엽전, 분당 처치(숫자 칸). 바꾸면 `result = {potion, coinPerMin?, killPerMin?, at}` → 800ms 뒤 `sendPick()`. 고른 빌드가 없으면 "추천 빌드 탭에서 [이걸로]를 누르면 여기에 저장돼요". `renderAll`에서 함께 그림. 이 입력은 `changed()`를 부르지 않는다(재계산 저장과 분리).
- [ ] **Step 2: 예시 결과** — `tools/example_profile.json`: 모든 스타일 강화 10, 모든 도술 보유, `slotCount` 8(`check.py`의 "전부 보유·강화 10"과 같은 구성). Run: `python analyze.py --local tools/example_profile.json > tools/example_recs.json` / Expected: `grounds` 5개가 든 JSON(파일 끝의 `# N초`는 stderr라 파일에 안 들어감). 분석 중 stdout 안내문(예: "커뮤니티 덱 받기 실패")이 섞이면 JSON이 깨지므로 `python -c "import json;json.load(open('tools/example_recs.json',encoding='utf-8'))"`로 읽히는지 확인. 결과에 닉네임이 없는지 확인(커뮤니티 덱 작성자 이름은 공개 게시판 표시 이름이라 그대로 둔다).
- [ ] **Step 3: 패치노트** — `patchnotes.json` 맨 앞에 `{"v": "4.1", "date": "<실행 날짜 MM/DD>", "items": [...]}`: 탭 2개, 사냥터별 생존·믹스·딜 추천과 커뮤니티 빌드, 도술 아이콘, [이걸로] 즉시 저장(재계산 없음), 하루 두 번 정기 재계산.
- [ ] **Step 4: 만들고 검사** — Task 8 Step 3과 같은 명령 / Expected: `ok`, `node --check` 오류 없음
- [ ] **Step 5: 브라우저 확인 (로컬)** — `../dokkaebi-dosa`에서 `python -m http.server 8765` 후 열어 확인(사용자에게도 같은 목록 전달):
  - PC 너비에서 탭 2개, 탭마다 한 화면 전체 사용
  - 사냥터 칩 5개, 보스에서 광역/단일 숨김, 다시 열면 마지막 사냥터
  - 카드 3장 가로, 아이콘 번호·금색·초록 테두리·마우스 올리면 이름
  - 커뮤니티 "N개 더 ▾", 미지정 목록, 영상 링크 새 창
  - 로그인 전 [이걸로] → 요청 없이 안내 문구, 새로고침해도 임시 저장본에 남음
  - 예전 결과만 있는 상태(브라우저 저장소의 이전 결과) → 예전 추천 트리 화면, 오류 없음
  - 좁은 화면(400px)에서 카드 세로, 가로 스크롤 없음
- [ ] **Step 6: 커밋** — dokkaebi-sim: `git add site tools && git commit -m "사이트: 내 수첩에 내 빌드 목록·돌려 본 결과, 예시 결과 다시 만듦"`
- [ ] **Step 7: 배포 (사용자 확인 후)** — dokkaebi-sim `git push`(check.yml 전체 점검 통과 확인: `gh run watch`), 서버 배포가 끝났는지 확인(Task 6), 그다음 dokkaebi-dosa `git add index.html patchnotes.json icons && git commit -m "v4.1 사냥터별 추천 빌드" && git push`. 정기 재계산 전이라도 ENGINE이 바뀌어 다음 분석 실행 때 모두 다시 계산된다. 원하면 `gh workflow run analyze.yml`로 바로 실행.
- [ ] **Step 8: 실제 사이트 확인** — 테스트 닉네임으로 불러오기 → 새 화면, [이걸로] → "내 빌드 저장됨", 길드원 현황의 저장 날짜가 바뀌지 않음(재계산 안 함), 다시 불러오면 내 빌드 유지.
