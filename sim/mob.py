# 몰이 사냥 모델 (몹 n마리 뭉침): 파멸 궁(대폭발+요기범람) / 연타 궁(폭주+격노)
# 계수·쿨은 data/skills.json(10/21 패치 공지·인게임 툴팁 0강) × (1 + 스타일 강화 계수)
import json, os, random
import transcend as TR
from timeline import charge_time
_D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
D = json.load(open(os.path.join(_D, "skills.json"), encoding="utf-8"))
TGT = json.load(open(os.path.join(_D, "targets.json"), encoding="utf-8"))
ST = [s["n"] for s in D["styles"]]
BY = {k["n"]: k for k in D["skills"]}
LVC = {x["level"]: x["coefficient"] for x in BY["사격"]["num"]["lv"]}
LVC[0] = 0.0
HEALS = {"생명의 축복", "생명의 흐름"}
AOE = set()
# 10/21: 얼음화살·쇠뇌 추가 피해가 '1회'(계수 합의 1/3)로, 영혼 소용돌이 저주 삭제, 파쇄·결계 받는 피해 5% → 10%
EFF = {"화염구": {"dot": "화상"}, "하늘의 심판": {"dot": "화상"},"번개 폭풍": {"dot": "감전"}, "얼음화살": {"eb": 1 / 3, "chill": 1}, "날카로운 얼음창": {"chill": 1},
       "쇠뇌 사격": {"bc": 1 / 3}, "낙뢰": {"elem": 1}, "화염 분출": {"elem": 1, "crack": 1}, "붕괴하는 대지": {"elem": 1},
       "연쇄 번개": {"elem": 1, "crack": 1}, "영혼 소용돌이": {"armor": 1}, "회전 난격": {"shatter": 1},
       "연쇄 타격": {"armor2": 1}, "공간 결계": {"vuln5": 1}}
ARMOR = 0.05
# 근거리 도술은 자동 사냥에서 몹에게 다가가는 시간이 붙음. 10/21 우물동굴 실측 3회(연타 궁 근접 몰이 vs 파멸 궁 원거리 몰이) 비율에 맞춘 값
MELEE_GAP = 2.5
NEAR = {k["n"] for k in D["skills"] if (k.get("q") or "").endswith("근거리")}
DOTV = {"화상": 2.0, "감전": 2.0, "저주": 0.0}   # 지속 피해(초당, 모델 단위). 10/21: 5 → 2, 저주 삭제
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
        K[k["n"]] = {"style": st, "dmg": dmg * tm, "cd": cd, "mot": (n.get("m") or 500) / 1000, "hits": hits, "chg": charge_time(k["n"], n)}
        if TGT.get(k["n"], 1) > 1: AOE.add(k["n"])
    # 폭주·대폭발 외 궁극기는 일반 도술처럼 근사(쿨·피해·대상 수만)
    for k in D["skills"]:
        if not k["u"] or not k.get("num") or k["n"] in ("폭주", "대폭발"): continue
        st = ST[k["st"]]; n = k["num"]
        hits = sum((d["hits"] or 1) for d in n.get("dc") or []) or 1
        K[k["n"]] = {"style": st, "dmg": total(k) * mult(st), "cd": n["cd"] or 60.0, "mot": (n.get("m") or 500) / 1000, "hits": hits, "chg": charge_time(k["n"], n), "u": True}
        if TGT.get(k["n"], 1) > 1: AOE.add(k["n"])
    POK = (total(BY["폭주"]) * mult("연타"), BY["폭주"]["num"]["cd"], 3.0, 11, 38.8)
    BIG = (total(BY["대폭발"]) * mult("파멸"), BY["대폭발"]["num"]["cd"], 0.6)

# 궁극기 → 신식 스타일. 트리에 그 스타일 도술이 3개 이상이면 그 신식으로 계산
ULT_MODE = {"폭주": "연타", "대폭발": "파멸", "천벌": "강타", "신내림": "주술", "회전하는 칼날": "기만"}

def mode_of(order):
    ult = next((x for x in order if x in ULT_MODE), None)
    # 궁극기 자신(천벌·신내림·회전하는 칼날은 K에 있음)은 세지 않음
    if ult and sum(K[k]["style"] == ULT_MODE[ult] for k in order if k in K and k != ult) >= 3:
        mode = ULT_MODE[ult]
    else:
        mode = "연타" if sum(K[k]["style"] == "연타" for k in order if k in K) >= 3 else "파멸"
    # 기동 신식(10/21): 도술마다 영력 10, 200이 되면 연속 쇄도 쿨 초기화 + 10초 [연쇄](궁극기 피해 +50%). 귀보(회피)는 자동 사냥이 안 쓰므로 뺌
    if "연속 쇄도" in order and sum(K[k]["style"] == "기동" for k in order if k in K and k != "연속 쇄도") >= 3:
        mode = "기동"
    return mode

def sim(order, n, T=300, cast="flat", Kc=20, dot_rage=True):
    mode = mode_of(order)
    # 강타(10/21): 시전마다 영력 10(최대 100), 33/66/100에서 피해 +3/7/10%, 가득 찬 채 궁극기를 쓰면 일반 도술 쿨 초기화
    # 주술(10/21): 시전마다 영력 8 → 30/60/90에서 구슬 1/2/3, 궁극기 +30/60/90%, 주술 도술을 쓰면 모든 도술 남은 쿨 0.1초×구슬 감소
    # 기만: 시전마다 눈물 1, 2개가 되면 방금 쓴 일반 도술 쿨 절반
    cg = 0; og = 0; tear = 0
    dash = 0; chain = -1
    cd = {k: 0.0 for k in order}; t = 0.0; tot = 0.0; idle = 0.0; u = {}; g = 0; yogi = -1
    rage = 0; last_hit = -99.0
    tg = lambda k: range(min(n, 5, TGT.get(k, 5))) if k in AOE else [0]   # 툴팁 대상 수(2·4인 등)까지만
    def ct(m):
        return 0.75 if cast == "flat" else max(m, 0.3) + 0.25   # 10/21: 요기범람 전개 속도 증가 삭제
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
                    am = 1 + ARMOR * ((u.get(("방깎", i), -1) > t) + (u.get(("방깎2", i), -1) > t)) + 0.10 * (u.get(("결계", i), -1) > t)
                    if k == "대폭발": tot += BIG[0] * mw * am
                    else:
                        d = POK[0] + (POK[3] * POK[4] if u.get(("화상", i), -1) > t else 0)
                        tot += d * am * rm()
                if k == "대폭발": cd[k] = t + BIG[1]; dt = ct(BIG[2])
                else: cd[k] = t + POK[1]; dt = ct(POK[2]); gain(POK[3] * min(n, 5))
            else:
                s = K[k]; e = EFF.get(k, {}); dt = ct(s["mot"]) + s["chg"] + (MELEE_GAP if k in NEAR else 0.0); h = t + dt
                sb = 1.0
                if mode == "강타":
                    sb = 1.10 if cg >= 100 else 1.07 if cg >= 66 else 1.03 if cg >= 33 else 1.0
                if mode == "주술" and s.get("u"):
                    ob = 3 if og >= 90 else 2 if og >= 60 else 1 if og >= 30 else 0
                    sb = 1 + 0.3 * ob
                for i in tg(k):
                    d = s["dmg"] * sb * (1.5 if k == "연속 쇄도" and t < chain else 1.0)
                    if e.get("eb") and u.get("원소", -1) > t: d *= 1 + e["eb"]
                    if e.get("bc") and u.get(("한기", i), -1) > t: d *= 1 + e["bc"]
                    m = 1 + 0.10 * (u.get(("파쇄", i), -1) > t) + 0.10 * (u.get(("파열", i), -1) > t) + 0.10 * (u.get(("결계", i), -1) > t) + ARMOR * ((u.get(("방깎", i), -1) > t) + (u.get(("방깎2", i), -1) > t))
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
                if mode == "강타":
                    if s.get("u") and cg >= 100:
                        cg = 0
                        for x in order:
                            if not K.get(x, {}).get("u") and x not in ("폭주", "대폭발"): cd[x] = min(cd[x], h)
                    else:
                        cg = min(100, cg + 10)
                if mode == "주술":
                    og = min(100, og + 8)
                    ob = 3 if og >= 90 else 2 if og >= 60 else 1 if og >= 30 else 0
                    if ob and s["style"] == "주술":
                        for x in order:
                            if cd[x] > h: cd[x] = max(h, cd[x] - 0.1 * ob)
                if mode == "기만":
                    tear = min(2, tear + 1)
                    if tear >= 2 and not s.get("u"):
                        cd[k] = t + max(s["cd"] * 0.5, dt); tear = 0
                if mode == "기동":
                    dash += 10
                    if dash >= 200:
                        dash = 0; chain = h + 10; cd["연속 쇄도"] = h
                if mode == "파멸" and s["style"] == "파멸" and not h < yogi:
                    g += 1
                    if g >= Kc:
                        g = 0; yogi = h + 30
                        for x in order:
                            if x != "대폭발": cd[x] = min(cd[x], h)
        dots = 0
        for i in range(n):
            for ty in ("화상", "감전"):
                if u.get((ty, i), -1) > t: tot += DOTV[ty] * dt * rm(); dots += 1
            if u.get(("저주", i), -1) > t: tot += DOTV["저주"] * dt * rm(); dots += 1
        if dot_rage and dots and mode == "연타": last_hit = t + dt
        t += dt
    return tot / T, idle / T

CONDS = [(c, k) for c in ("flat", "motion") for k in (20, 35)]   # 요기범람까지 파멸 시전 수(10/21: 영력 25 → 10이라 8·14 → 20·35)
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
    return sim(o, 5, 300, "flat", 20)[0] * (GATHER_BONUS if gathered(o) else 1.0)
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
