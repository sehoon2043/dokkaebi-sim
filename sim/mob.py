# 몰이 사냥 모델 (몹 n마리 뭉침): 파멸 궁(대폭발+요기범람) / 연타 궁(폭주+격노)
# 계수는 data/skills.json(10/14 인게임 툴팁 0강 환산) × (1 + 스타일 강화 계수)
import json, os, random
import transcend as TR
_D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
D = json.load(open(os.path.join(_D, "skills.json"), encoding="utf-8"))
TGT = json.load(open(os.path.join(_D, "targets.json"), encoding="utf-8"))
ST = [s["n"] for s in D["styles"]]
BY = {k["n"]: k for k in D["skills"]}
LVC = {x["level"]: x["coefficient"] for x in BY["사격"]["num"]["lv"]}
LVC[0] = 0.0
HEALS = {"생명의 축복", "생명의 흐름"}
AOE = set()
EFF = {"화염구": {"dot": "화상"}, "번개 폭풍": {"dot": "감전"}, "얼음화살": {"eb": 0.348, "chill": 1}, "날카로운 얼음창": {"chill": 1},
       "쇠뇌 사격": {"bc": 0.181}, "낙뢰": {"elem": 1}, "화염 분출": {"elem": 1, "crack": 1}, "붕괴하는 대지": {"elem": 1},
       "연쇄 번개": {"elem": 1, "crack": 1}, "영혼 소용돌이": {"curse": 15, "armor": 1}, "회전 난격": {"shatter": 1},
       "연쇄 타격": {"armor2": 1}, "공간 결계": {"vuln5": 1}}
ARMOR = 0.05
DS, DA, DE = 5, 5, 10
K = {}; POK = None; BIG = None

def total(k):
    n = k["num"]; t = n.get("total")
    if t: return t
    if n.get("dc"):
        c = n["dc"][-1]; return c["basic_coefficient"] * (c["hits"] or 1)
    return 0.0

def setup(levels, steps=None):
    """스타일 강화 레벨(dict)·돌파 단계(dict)로 K·POK·BIG 구성"""
    global POK, BIG
    K.clear(); AOE.clear()
    def mult(st): return 1 + LVC.get(int(levels.get(st, 0) or 0), 0.0)
    for k in D["skills"]:
        if k["u"] or not k.get("num"): continue
        st = ST[k["st"]]; n = k["num"]
        hits = sum((d["hits"] or 1) for d in n.get("dc") or []) or 1
        dmg = 0.0 if k["n"] in HEALS else total(k) * mult(st)
        cd0 = n["cd"] or 30.0
        cd, tm = TR.effect(k["n"], (steps or {}).get(k["n"], 0), cd0)
        K[k["n"]] = {"style": st, "dmg": dmg * tm, "cd": cd, "mot": (n.get("m") or 500) / 1000, "hits": hits}
        if TGT.get(k["n"], 1) > 1: AOE.add(k["n"])
    # 폭주·대폭발 외 궁극기는 일반 도술처럼 근사(쿨·피해·대상 수만)
    for k in D["skills"]:
        if not k["u"] or not k.get("num") or k["n"] in ("폭주", "대폭발"): continue
        st = ST[k["st"]]; n = k["num"]
        hits = sum((d["hits"] or 1) for d in n.get("dc") or []) or 1
        K[k["n"]] = {"style": st, "dmg": total(k) * mult(st), "cd": n["cd"] or 60.0, "mot": (n.get("m") or 500) / 1000, "hits": hits}
        if TGT.get(k["n"], 1) > 1: AOE.add(k["n"])
    POK = (total(BY["폭주"]) * mult("연타"), 50.0, 3.0, 11, 40.19)
    BIG = (total(BY["대폭발"]) * mult("파멸"), 138.0, 0.6)

def sim(order, n, T=300, cast="flat", Kc=8, dot_rage=True):
    mode = "연타" if sum(K[k]["style"] == "연타" for k in order if k in K) >= 3 else "파멸"
    cd = {k: 0.0 for k in order}; t = 0.0; tot = 0.0; idle = 0.0; u = {}; g = 0; yogi = -1
    rage = 0; last_hit = -99.0
    tg = lambda k: range(min(n, 5)) if k in AOE else [0]
    def ct(m):
        x = 0.75 if cast == "flat" else max(m, 0.3) + 0.25
        return x / 1.5 if t < yogi else x
    def rm(): return 1 + 0.004 * rage if mode == "연타" else 1.0
    def gain(cnt):
        nonlocal rage, last_hit
        if mode == "연타" and cnt > 0: rage = min(50, rage + cnt); last_hit = t
    while t < T:
        if mode == "연타" and t - last_hit > 3: rage = 0
        ready = [k for k in order if cd[k] <= t]
        if not ready:
            dt = 0.75; tot += 52.0; idle += dt
        else:
            k = ready[0]; mw = 1.10 if t < yogi else 1.0
            if k in ("대폭발", "폭주"):
                for i in range(min(n, 5)):
                    am = 1 + ARMOR * ((u.get(("방깎", i), -1) > t) + (u.get(("방깎2", i), -1) > t)) + 0.05 * (u.get(("결계", i), -1) > t)
                    if k == "대폭발": tot += BIG[0] * mw * am
                    else:
                        d = POK[0] + (POK[3] * POK[4] if u.get(("화상", i), -1) > t else 0)
                        tot += d * am * rm()
                if k == "대폭발": cd[k] = t + 138.0; dt = ct(BIG[2])
                else: cd[k] = t + POK[1]; dt = ct(POK[2]); gain(POK[3] * min(n, 5))
            else:
                s = K[k]; e = EFF.get(k, {}); dt = ct(s["mot"]); h = t + dt
                for i in tg(k):
                    d = s["dmg"]
                    if e.get("eb") and u.get("원소", -1) > t: d *= 1 + e["eb"]
                    if e.get("bc") and u.get(("한기", i), -1) > t: d *= 1 + e["bc"]
                    m = 1 + 0.05 * (u.get(("파쇄", i), -1) > t) + 0.05 * (u.get(("파열", i), -1) > t) + 0.05 * (u.get(("결계", i), -1) > t) + ARMOR * ((u.get(("방깎", i), -1) > t) + (u.get(("방깎2", i), -1) > t))
                    tot += d * m * mw * rm()
                    if "dot" in e: u[(e["dot"], i)] = h + 10
                    if "chill" in e: u[("한기", i)] = h + 5
                    if "crack" in e and u.get(("파쇄src", i), -1) > t: u[("파쇄", i)] = h + 10
                    if "shatter" in e: u[("파쇄src", i)] = h + DS
                    if "rsrc" in e: u[("파열src", i)] = h + 10
                    if "rupt" in e and u.get(("파열src", i), -1) > t: u[("파열", i)] = h + 10
                    if "curse" in e: u[("저주", i)] = max(u.get(("저주", i), -1), h + e["curse"])
                    if "armor" in e: u[("방깎", i)] = h + DA
                    if "armor2" in e: u[("방깎2", i)] = h + DA
                    if "vuln5" in e: u[("결계", i)] = h + 5
                if "elem" in e: u["원소"] = h + DE
                cd[k] = t + s["cd"]
                gain(s.get("hits", 1) * len(list(tg(k))))
                if mode == "파멸" and s["style"] == "파멸" and not h < yogi:
                    g += 1
                    if g >= Kc:
                        g = 0; yogi = h + 20
                        for x in order:
                            if x != "대폭발": cd[x] = min(cd[x], h)
        dots = 0
        for i in range(n):
            for ty in ("화상", "감전"):
                if u.get((ty, i), -1) > t: tot += 5.0 * dt * rm(); dots += 1
            if u.get(("저주", i), -1) > t: tot += 7.0 * dt * rm(); dots += 1
        if dot_rage and dots and mode == "연타": last_hit = t + dt
        t += dt
    return tot / T, idle / T

CONDS = [(c, k) for c in ("flat", "motion") for k in (8, 14)]
def sc(o, n): return sum(sim(o, n, 300, c, k)[0] for c, k in CONDS) / len(CONDS)
# 몹 모으기: 공간 결계가 있으면 거의 항상 5마리가 뭉치고 다시 모이는 시간도 줄어듦
# 보정값은 엽전 비경 2단계 실측(10/14, 같은 캐릭터 3회: 결계 없는 몰이 49.2만/시간, 결계+소용돌이+힐 45.7만·50.3만)에 맞춤
GATHER = "공간 결계"
GATHER_BONUS = 1.065
def gathered(o): return GATHER in o
def w(o):
    if gathered(o): return GATHER_BONUS * sc(o, 5)
    return 0.2 * sc(o, 3) + 0.8 * sc(o, 5)
def quick(o):
    """간이 점수(5마리, 한 조건)"""
    return sim(o, 5, 300, "flat", 8)[0] * (GATHER_BONUS if gathered(o) else 1.0)
def idle(o): return sum(sim(o, 5, 300, c, k)[1] for c, k in CONDS) / len(CONDS)

def valid_order(c):
    if "영혼 소용돌이" in c and c.index("영혼 소용돌이") > 1: return False
    if "화염구" in c and "폭주" in c and c.index("화염구") > c.index("폭주"): return False
    return True

def opt(o, it=200, seed=11):
    r = random.Random(seed); b = w(o); bo = o
    for _ in range(it):
        c = bo[:]; i, j = r.sample(range(len(c)), 2); c.insert(j, c.pop(i))
        if not valid_order(c): continue
        v = w(c)
        if v > b: b, bo = v, c
    return b, bo
