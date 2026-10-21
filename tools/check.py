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
    ok(M.EFF.get("공간 결계", {}).get("vuln5") == 1, "공간 결계의 받는 피해 +5%가 몰이 계산에서 빠짐")


# ---------- 3. 계산 모델 성질 ----------
ALL = {k["n"]: {} for k in D["skills"]}
PROFILES = {
    "전부 보유·강화 10": {"levels": {s: 10 for s in STYLES}, "owned": ALL},
    "전부 보유·강화 20·돌파 3": {"levels": {s: 20 for s in STYLES}, "owned": {n: {"br": 3} for n in ALL}},
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
    setup({"levels": p["levels"], "owned": {n: {"br": 5} for n in ALL}})
    for k, f in fs.items():
        ok(f() >= base[k] - 1e-9, f"{k} 점수가 돌파를 올렸는데 줄어듦")
    # 공간 결계 보정은 결계가 있을 때만
    setup(p)
    o2 = [x for x in mo]
    if M.GATHER not in o2:
        ok(abs(M.quick(o2) - M.sim(o2, 5, 300, "flat", 20)[0]) < 1e-9, "공간 결계 없이도 모으기 보정이 들어감")


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
    ok(not [n for n in r["notes"] if "오류" in n], f"분석 메모에 오류: {r['notes']}")
    for t in r["trees"]:
        tree_checks(t, set(p["owned"]), "작은 프로필")


if __name__ == "__main__":
    for name, fn in (("데이터", data_checks), ("효과 표 이름", name_checks), ("계산 모델", model_checks), ("결과 형식", result_checks)):
        if name == "결과 형식" and "--quick" in sys.argv:
            continue
        n0 = len(FAIL)
        fn()
        print(f"{name}: " + ("통과" if len(FAIL) == n0 else f"실패 {len(FAIL) - n0}개"))
    for f in FAIL:
        print("  -", f)
    sys.exit(1 if FAIL else 0)
