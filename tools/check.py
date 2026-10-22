# 계산 자동 점검: 데이터 오타·누락, 계산 모델의 기본 성질, 결과 형식을 확인한다
#   python tools/check.py          → 하나라도 실패하면 종료 코드 1 (GitHub Actions에서 분석 전에 실행)
#   python tools/check.py --quick  → 결과 형식 점검(분석 1회)을 건너뛴다
import json, math, os, sys
sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "sim"))
import analyze as A
import explain as EX
import field as F
import mob as M
import verify as VF
import sustain as SU
import gamedata

S = F.S
FAIL = []


def ok(cond, msg):
    if not cond:
        FAIL.append(msg)
    return cond


def load(name):
    return gamedata.load(name)   # 비공개 데이터는 저장 서버에서 받아 옴


D = load("skills.json")
NAMES = {k["n"] for k in D["skills"]}
STYLES = [s["n"] for s in D["styles"]]
STYLE_OF = {k["n"]: STYLES[k["st"]] for k in D["skills"]}


# ---------- 1. 데이터 ----------
def data_checks():
    ok(len(STYLES) == 12, "스타일이 12개가 아님")
    ok(len(NAMES) == len(D["skills"]), "도술 이름 중복")
    for k in D["skills"]:
        n = k["n"]
        if not ok(0 <= k["st"] < len(STYLES), f"{n}: 스타일 번호 오류"):
            continue
        num = k.get("num")
        if not ok(num is not None, f"{n}: 수치(num) 없음"):
            continue
        for d in num.get("dc") or []:
            ok((d.get("hits") or 1) >= 1 and d["basic_coefficient"] >= 0, f"{n}: 피해 계수·타수 오류")
        t = S.total(k)
        ok(math.isfinite(t) and t >= 0, f"{n}: 총 피해 계수 오류")
        lv = [x["coefficient"] for x in sorted(num.get("lv") or [], key=lambda x: x["level"])]
        ok(all(a <= b for a, b in zip(lv, lv[1:])), f"{n}: 강화 계수가 레벨에 따라 줄어듦")
    # 인게임 툴팁으로 확인한 값
    ok([d["hits"] for d in A.F.S.BY["날카로운 얼음창"]["num"]["dc"]] == [5], "날카로운 얼음창 타수가 5가 아님")
    tr = load("transcend.json")
    for n, t in tr.items():
        ok(n in NAMES, f"돌파 표: 없는 도술 이름 '{n}'")
        ok(len(t["dmg"]) <= 10 and len(t["cd"]) <= 10, f"돌파 표: {n} 단계가 10개 넘음")
        ok(all(a <= b for a, b in zip(t["dmg"], t["dmg"][1:])), f"돌파 표: {n} 피해 증가가 단계마다 줄어듦")
        ok(all(a <= b for a, b in zip(t["cd"], t["cd"][1:])), f"돌파 표: {n} 쿨 감소가 단계마다 줄어듦")
        if n in NAMES and t["cd"]:
            cd = A.F.S.BY[n]["num"]["cd"] or 0
            ok(not cd or t["cd"][-1] < cd, f"돌파 표: {n} 쿨 감소가 쿨타임보다 큼")
    tg = load("targets.json")
    for n, v in tg.items():
        ok(n in NAMES, f"대상 수 표: 없는 도술 이름 '{n}'")
        ok(isinstance(v, int) and 1 <= v <= 30, f"대상 수 표: {n} 값 {v} 이상함")


# ---------- 2. 효과 표의 도술 이름 (오타면 효과가 조용히 빠짐) ----------
def name_checks():
    def names(where, it):
        for n in it:
            ok(n in NAMES, f"{where}: 없는 도술 이름 '{n}'")

    def keyed(where, it):
        for key in it:
            st, n = key.split("/", 1)
            ok(n in NAMES and STYLE_OF.get(n) == st, f"{where}: '{key}' 스타일/이름 불일치")

    names("몰이 효과(mob.EFF)", M.EFF)
    names("연계 조건(timeline.COND)", S.COND)
    names("효과 부여(timeline.APPLY)", S.APPLY)
    names("받는 피해(timeline.VULN)", S.VULN)
    names("원소(timeline.SELF_ELEM)", S.SELF_ELEM)
    names("방어력 감소(timeline.ARMOR_SRC)", S.ARMOR_SRC)
    names("힐", F.HEALS | M.HEALS)
    names("공간 결계", [M.GATHER])
    names("연타 광역(analyze.YT_AOE)", A.YT_AOE)
    names("설명 효과(explain.GIVE)", EX.GIVE)
    names("설명 연계(explain.NEED)", [x[0] for x in EX.NEED])
    keyed("받는 피해 증가(AMP_HIT)", S.AMP_HIT)
    keyed("버프(BUFF_DMG)", S.BUFF_DMG)
    keyed("쿨 감소 버프(BUFF_CD)", S.BUFF_CD)
    keyed("상태 이상 종류(STATUS_BY)", [x for g in S.STATUS_BY for x in g])
    for k in S.APPLY.values():
        for x in k:
            ok(x in S.DOT or x in S.DUR or x in ("낙인", "관통", "충격", "파쇄", "파열", "동상", "출혈", "화상", "감전", "약화"), f"효과 부여: 모르는 효과 '{x}'")
    ok(M.EFF.get("공간 결계", {}).get("vuln5") == 1, "공간 결계의 받는 피해 +10%가 몰이 계산에서 빠짐")
    # 몰이 계산에도 보스·필드(timeline)와 같은 연계가 들어가야 함(광역 도술끼리 이어지는 것)
    for n in ("휘둘러 내려치기", "회전 난격", "휘둘러치기"):
        ok(M.EFF.get(n, {}).get("shatter"), f"몰이 계산: {n}의 파쇄 부여가 빠짐")
    for n in ("크게 베기", "검기 날리기"):
        ok(M.EFF.get(n, {}).get("rsrc"), f"몰이 계산: {n}의 파열 부여가 빠짐")
    for n in ("내려찍기", "내려치기"):
        ok(M.EFF.get(n, {}).get("rupt"), f"몰이 계산: {n}의 파열 대상 받는 피해 +10%가 빠짐")
    for n, ty in (("화염구", "화상"), ("하늘의 심판", "화상"), ("번개 폭풍", "감전"), ("일섬", "감전")):
        ok(M.EFF.get(n, {}).get("dot") == ty, f"몰이 계산: {n}의 {ty} 지속 피해가 빠짐")


# ---------- 2-1. 유지력(회복·보호막) 표 ----------
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


# ---------- 3. 계산 모델 성질 ----------
ALL = {k["n"]: {} for k in D["skills"]}
# 수첩의 br = 각성(도술 별 단계, 캐릭터 능력치만 오름). 도술 피해·쿨이 바뀌는 돌파는 dp(아직 입력 칸 없음)
PROFILES = {
    "전부 보유·강화 10": {"levels": {s: 10 for s in STYLES}, "owned": ALL},
    "전부 보유·강화 20·돌파 3": {"levels": {s: 20 for s in STYLES}, "owned": {n: {"dp": 3} for n in ALL}},
}


def setup(p):
    lv = {k: int(v or 0) for k, v in p["levels"].items()}
    st = A.TR.steps_of(p["owned"])
    F.set_levels(lv)
    F.set_steps(st)
    M.setup(lv, st)
    F.REF[0] = 290.0


def model_checks():
    p = PROFILES["전부 보유·강화 10"]
    owned = set(p["owned"])
    setup(p)
    bs = F.boss_search(owned, seeds=2)
    rng = F.search(owned, "ranged", False, seeds=2)
    mob = A.mob_search(owned, 0)
    if not (ok(bs, "보스 탐색 결과 없음") and ok(rng, "필드 탐색 결과 없음") and ok(mob, "몰이 탐색 결과 없음")):
        return
    _, bc, bo = bs[0]
    # 파멸 궁극기 트리는 요기(쿨 초기화) 주기 때문에 쿨이 줄면 점수가 줄 수 있어서(실제 자동 사냥도 같음) 단조성 점검에서 뺀다
    rng = [r for r in rng if "대폭발" not in r[2]] or rng
    _, rc, ro = rng[0]
    mo = mob[1]
    fs = {"보스": lambda: F.boss_score(bc, bo), "필드": lambda: F.kills(rc, ro, 0.3), "몰이": lambda: M.w(mo)}
    base = {k: f() for k, f in fs.items()}
    for k, v in base.items():
        ok(math.isfinite(v) and v > 0, f"{k} 점수가 0 이하이거나 숫자가 아님")
        ok(abs(fs[k]() - v) < 1e-9, f"{k} 점수가 같은 입력에 다르게 나옴")
    # 다른 계산을 섞어 불러도 값이 그대로인지(전역 상태 누수)
    F.kills(rc, ro, 0.7)
    F.boss_score(rc + [], ro)
    M.w(mo)
    for k, f in fs.items():
        ok(abs(f() - base[k]) < 1e-9, f"{k} 점수가 다른 계산 뒤에 달라짐(전역 상태 누수)")
    # 가정 흔들기 후 원래대로 돌아오는지
    for name, _, ap in VF.SCENS:
        undo = ap()
        undo()
    for k, f in fs.items():
        ok(abs(f() - base[k]) < 1e-9, f"{k} 점수가 가정 흔들기 뒤에 원래대로 안 돌아옴")
    # 강화를 올리면 점수가 줄지 않아야 함
    up = {"levels": {s: 15 for s in STYLES}, "owned": ALL}
    setup(up)
    for k, f in fs.items():
        ok(f() >= base[k] - 1e-9, f"{k} 점수가 강화를 올렸는데 줄어듦")
    # 돌파를 올리면 점수가 줄지 않아야 함
    setup({"levels": p["levels"], "owned": {n: {"dp": 5} for n in ALL}})
    for k, f in fs.items():
        ok(f() >= base[k] - 1e-9, f"{k} 점수가 돌파를 올렸는데 줄어듦")
    # 주술 신식 3단계(10/21 툴팁): 구슬은 신내림의 강화 저주·폭발 피해만 +30/60/90%, 직접 피해(179.1%×6)에는 안 붙음
    setup({"levels": {}, "owned": {}})
    ju = [n for n in ("부적 던지기", "살 날리기", "저주 내리기") if n in NAMES] + ["화염구", "낙뢰"]
    u, mem, od = S.build(ju, F.LV, 0.0)
    sin = next((v for v in od if v["n"] == "신내림"), None)
    if ok(u == "신내림" and sin, "주술 3개 트리의 궁극기가 신내림이 아님"):
        burst, dot = S.CURSE["신내림"]
        ok(abs(sin["damage"] - (1074.6 + burst + dot)) < 0.5, f"신내림 피해에 강화 저주 폭발·지속 피해가 빠짐 ({sin['damage']:.1f})")
        orb = S.Orbs()
        orb.g = 90
        want = 1 + 0.9 * (burst + dot) / (1074.6 + burst + dot)
        ok(abs(orb.bonus(None, sin) - want) < 1e-6, f"구슬 3개 보너스가 신내림 직접 피해에도 붙음 ({orb.bonus(None, sin):.3f}, 기대 {want:.3f})")
        big = dict(sin, n="대폭발", orb_frac=0.0)
        big.pop("orb_frac")
        ok(orb.bonus(None, big) == 1.0, "강화 저주가 없는 궁극기에 구슬 보너스가 붙음")
    ok(abs(M.K["신내림"]["dmg"] - 1074.6) < 0.5 and M.K["신내림"].get("curse", 0) > 0, "몰이 계산: 신내림 직접 피해·강화 저주 분리가 안 됨")
    o_sin = ["영혼 소용돌이", "부적 던지기", "살 날리기", "저주 내리기", "신내림", "화염구", "낙뢰", "번개 폭풍"]
    a1 = M.w(o_sin)
    M.CURSE_HITS = 5
    a5 = M.w(o_sin)
    M.CURSE_HITS = 1
    ok(a5 > a1, "몰이 계산: 강화 저주 폭발이 여러 몹에게 들어가는 가정이 점수에 반영 안 됨")
    # 각성(br)은 캐릭터 능력치만 올리고 도술 피해·쿨은 그대로(10/09 사용자 확인, 사이트 안내문도 같음)
    setup({"levels": p["levels"], "owned": {n: {"br": 5} for n in ALL}})
    for k, f in fs.items():
        ok(abs(f() - base[k]) < 1e-9, f"{k} 점수가 각성(br)에 따라 바뀜 — 각성은 도술 피해·쿨에 영향 없음")
    # 공간 결계 보정은 결계가 있을 때만
    setup(p)
    o2 = [x for x in mo]
    if M.GATHER not in o2:
        ok(abs(M.quick(o2) - M.sim(o2, 5, 300, "flat", 20)[0]) < 1e-9, "공간 결계 없이도 모으기 보정이 들어감")
    # 시전 횟수(유지력 계산용): 생명의 흐름 쿨 15초면 300초에 약 20회(요기범람·강압 쿨 초기화로 조금 더), 세기 전후 점수 그대로
    mo_h = ["생명의 흐름"] + [x for x in mo if x not in F.HEALS][:7]
    c = M.casts(mo_h)
    ok(10 <= c.get("생명의 흐름", 0) <= 25, f"몰이 시전 횟수: 생명의 흐름(쿨 15초) 300초 {c.get('생명의 흐름')}회")
    ok(abs(M.w(mo) - base["몰이"]) < 1e-9, "몰이: 시전 횟수 세기 뒤 점수가 달라짐")
    c2 = F.casts(rc + ["생명의 흐름"], ["생명의 흐름"] + ro)
    ok(10 <= c2.get("생명의 흐름", 0) <= 20, f"필드 시전 횟수: 생명의 흐름 300초 {c2.get('생명의 흐름')}회")
    ok(abs(F.kills(rc, ro, 0.3) - base["필드"]) < 1e-9, "필드: 시전 횟수 세기 뒤 점수가 달라짐")


# ---------- 4. 결과 형식 ----------
def tree_checks(t, owned, where):
    tid = t["id"]
    sl = t["slots"]
    ok(len(sl) == 8 and len(set(sl)) == 8, f"{where} {tid}: 칸이 8개가 아니거나 중복")
    ok(t["ult"] not in sl and t["ult"] in t["order"], f"{where} {tid}: 궁극기 위치 오류")
    ok(sorted(x for x in t["order"] if x != t["ult"]) == sorted(sl), f"{where} {tid}: 칸과 사용 순서가 다름")
    if not tid.startswith("comm_"):
        ok(all(x in owned for x in sl), f"{where} {tid}: 안 배운 도술이 들어감")
        us = STYLE_OF.get(t["ult"])
        ok(sum(STYLE_OF.get(x) == us for x in sl[:5]) >= 3, f"{where} {tid}: 하단 5칸에 궁극기 스타일이 3개 미만")
    for s in str(t.get("stat", "")).split(" · "):
        ok("nan" not in s and "inf" not in s, f"{where} {tid}: 숫자 오류 '{s}'")
    v = t.get("verify")
    if v:
        ok(not v["miss"], f"{where} {tid}: 탐색 보강 뒤에도 더 나은 조합이 남음 {v['miss']}")


def result_checks():
    p = {"levels": {"저격": 10, "파멸": 10, "절명": 5, "연타": 5}, "owned": {n: {} for n in ALL if STYLE_OF[n] in ("저격", "파멸", "절명", "연타", "헌신", "주술", "기만")}}
    r = A.analyze(p)
    ok(r["trees"], "작은 프로필 분석 결과에 트리가 없음")
    # 계산 방식 버전: 예전 방식 결과는 다시 계산 대상
    ok(r.get("engine") == A.ENGINE, "분석 결과에 계산 방식 버전(engine)이 없음")
    d = {"owned": {"사격": {}}}
    ok(not A.stale({"updatedAt": "1", "resultFor": "1", "result": r, "data": d}), "지금 방식으로 계산한 결과를 다시 계산하려 함")
    ok(A.stale({"updatedAt": "1", "resultFor": "1", "result": {"trees": []}, "data": d}), "예전 방식(engine 없음) 결과를 다시 계산하지 않음")
    ok(A.stale({"updatedAt": "2", "resultFor": "1", "result": r, "data": d}), "새로 저장한 프로필을 다시 계산하지 않음")
    ok(not A.stale({"updatedAt": "2", "resultFor": "", "result": None, "data": {}}), "배운 도술이 없는(비운) 프로필을 계산하려 함")
    ok(not [n for n in r["notes"] if "오류" in n], f"분석 메모에 오류: {r['notes']}")
    for t in r["trees"]:
        tree_checks(t, set(p["owned"]), "작은 프로필")
    # 10/21 패치로 생명의 흐름(공격력 12%×5, 쿨 15초)이 축복(35%, 쿨 20초)보다 초당 회복 2배 이상 → 필드 힐 트리도 흐름
    by = {t["id"]: t for t in r["trees"]}
    for tid in ("pureh", "singleh", "jhunt_h"):
        if tid in by:
            ok("생명의 흐름" in by[tid]["order"], f"작은 프로필 {tid}: 생명의 흐름을 배웠는데 힐이 흐름이 아님")
    # 힐 트리는 힐을 사용 순서 맨 앞에(게임에서 체력 조건을 걸어 필요할 때 쓰는 방식)
    for tid in ("mobheal", "mobheal2", "pureh", "singleh", "jhunt_h"):
        if tid in by:
            o = by[tid]["order"]
            hs = [x for x in o if x in F.HEALS]
            ok(hs and o[:len(hs)] == hs, f"작은 프로필 {tid}: 힐이 사용 순서 맨 앞이 아님 {o}")
    if "mobheal2" in by:
        ok(by["mobheal2"]["order"][0] == "생명의 흐름", "작은 프로필 mobheal2: 회복량이 큰 생명의 흐름이 맨 앞이 아님")


# ---------- 5. 실측 재현 (보정값이 실측에서 벗어나지 않았는지) ----------
# 10/21 절명 신식3 허수아비(다후 노강, 5분 02초): 도술별 (횟수, 피해 비중 %)
MEAS_1021 = {"order": ["휘둘러 내려치기", "화염 분출", "사격", "꿰뚫는 저격", "내려찍기", "암습", "찌르기", "크게 베기", "약점 베기"],
             "sec": 302.0,
             "hit": {"암습": (31, 37.4), "평타": (213, 10.3), "사격": (62, 7.5), "꿰뚫는 저격": (20, 7.4), "약점 베기": (24, 7.4),
                     "휘둘러 내려치기": (48, 6.7), "찌르기": (39, 6.6), "내려찍기": (39, 6.5), "크게 베기": (27, 6.2), "화염 분출": (32, 4.1)}}


def replay(P, meas):
    """보스 모델로 실측 트리를 다시 돌려 도술별 (횟수, 비중 %)"""
    m, k, c = P
    S.CD_RED = c
    S.AMP_HIT.clear()
    S.AMP_HIT.update(F.AMP0)
    S.BASIC, S.BASIC_I = F.BASIC_BOSS, F.BASIC_I
    o = meas["order"]
    u = next(x for x in o if A.F.S.BY[x]["u"])
    names = A.arrange(o, u)
    _, mem, od = S.build(names, F.LV, F.OH_BOSS)
    for v in od:
        if v["u"] and v["style"] == "절명":
            v["damage"] *= k
        elif v["style"] == "저격":
            v["damage"] *= m
    od.sort(key=lambda v: o.index(v["n"]))
    sim = S.Sim([dict(x) for x in od], mem, meas["sec"])
    cnt, dmg = {}, {}
    cast0, wait0 = sim.cast, sim.wait

    def cast(s):
        t0 = sim.total
        cast0(s)
        cnt[s["n"]] = cnt.get(s["n"], 0) + 1
        dmg[s["n"]] = dmg.get(s["n"], 0) + sim.total - t0

    def wait():
        t0, n0 = sim.total, sim.now
        r = wait0()
        cnt["평타"] = cnt.get("평타", 0) + round((sim.now - n0) / S.BASIC_I)
        dmg["평타"] = dmg.get("평타", 0) + sim.total - t0
        return r

    sim.cast, sim.wait = cast, wait
    sim.run()
    S.BASIC = 0.0
    tot = sum(dmg.values())
    return {x: (cnt.get(x, 0), dmg.get(x, 0) / tot * 100) for x in set(cnt) | set(dmg)}


# 10/21 우물동굴 215k 몰이 실측 3회(다후 노강, 8~10분씩): 트리별 처치 속도 비율이 몰이 점수 비율과 맞아야 함
MOB_1021 = {
    "1 연타 궁": ["연쇄 타격", "회전 난격", "화염 분출", "화염구", "크게 베기", "난타", "공간 결계", "폭주", "생명의 흐름"],
    "2 파멸 궁·대검 찍기": ["생명의 흐름", "공간 결계", "검기 폭발", "연쇄 번개", "요기 폭발", "번개 폭풍", "하늘의 심판", "대검 찍기", "대폭발"],
    "3 파멸 궁·방패 밀기": ["생명의 흐름", "방패 밀기", "공간 결계", "검기 폭발", "연쇄 번개", "요기 폭발", "번개 폭풍", "하늘의 심판", "대폭발"],
}
MOB_RATIO = [("2 파멸 궁·대검 찍기", "1 연타 궁", 1.185), ("3 파멸 궁·방패 밀기", "2 파멸 궁·대검 찍기", 0.935)]   # 엽전·처치 비율 평균


def measure_checks():
    setup({"levels": {}, "owned": {}})
    sc = {k: M.w(o) for k, o in MOB_1021.items()}
    for a, b, want in MOB_RATIO:
        r = sc[a] / sc[b]
        ok(abs(r / want - 1) <= 0.07, f"우물동굴 실측 재현: 몰이 점수 {a} / {b} = {r:.3f}, 실측 {want} (±7% 안이어야 함)")
    meas = MEAS_1021
    for P in F.BOSS_P:
        r = replay(P, meas)
        e = sum((r.get(x, (0, 0))[1] - p) ** 2 for x, (_, p) in meas["hit"].items())
        ok(e < 2.5, f"10/21 실측 재현: 보정값 {P}에서 도술별 피해 비중 오차(제곱합) {e:.1f} — 2.5 미만이어야 함")
        for x, (c0, _) in meas["hit"].items():
            c = r.get(x, (0, 0))[0]
            lim = max(2, round(c0 * 0.05))
            ok(abs(c - c0) <= lim, f"10/21 실측 재현: 보정값 {P}에서 {x} 횟수 {c}회(실측 {c0}회, 허용 ±{lim})")


if __name__ == "__main__":
    # --only 이름: 그 섹션만 실행(예: --only 유지력)
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for name, fn in (("데이터", data_checks), ("효과 표 이름", name_checks), ("유지력", sustain_checks), ("계산 모델", model_checks),
                     ("실측 재현", measure_checks), ("결과 형식", result_checks)):
        if name == "결과 형식" and "--quick" in sys.argv:
            continue
        if only and name != only:
            continue
        n0 = len(FAIL)
        fn()
        print(f"{name}: " + ("통과" if len(FAIL) == n0 else f"실패 {len(FAIL) - n0}개"))
    for f in FAIL:
        print("  -", f)
    sys.exit(1 if FAIL else 0)
