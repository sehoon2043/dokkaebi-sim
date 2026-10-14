# 필드 사냥 처치 속도 모델 + 보스 DPS 모델 (jmodel 기반)
# 처치 속도: 피해 이벤트를 몹 체력 H씩 순서대로 적용(남는 피해 버림), 처치마다 이동 시간 추가
import inspect, random
import jmodel as S

S.FORMS_STYLE_ONLY, S.FORMS_PER_CAST, S.STRICT_MAX = False, True, True
AMP0 = dict(S.AMP_HIT)
EV = []
_src = inspect.getsource(S.run).replace("def run(", "def run_ev(", 1)
_src = _src.replace('        tot += pick["damage"] * mult * vm\n', '        tot += pick["damage"] * mult * vm; EV.append((now, pick["damage"] * mult * vm))\n')
_src = _src.replace('gain = 1 if FORMS_PER_CAST else pick["hits"]', 'gain = (1 if FORMS_PER_CAST else pick["hits"]) if pick["damage"] > 0 else 0')
exec(_src, S.__dict__)
S.__dict__["EV"] = EV

OH = 0.3
HEALS = {"생명의 축복", "생명의 흐름"}
LV = {"*": 0}
HUNT_P = [(0.8, 0.55, 5), (0.9, 0.6, 5)]
BOSS_P = [(0.8, 0.55, 5), (0.75, 0.5, 5), (0.85, 0.55, 5), (0.8, 0.55, 4)]
HS = (1.5, 3.0, 5.0)
T = 300
REF = [290.0]


def set_levels(levels):
    LV.clear()
    LV.update({k: int(v or 0) for k, v in levels.items()})
    LV["*"] = 0


def style(n):
    return S.ST[S.BY[n]["st"]]


def pool(owned):
    return [k["n"] for k in S.D["skills"] if not k["u"] and k.get("num") and S.total(k) > 0 and k["num"]["cd"]
            and k["n"] in owned and k["n"] != "은신"]


def _prep(names, P):
    m, k, c = P
    S.CD_RED = c
    dn = [n for n in names if n not in HEALS]
    u, mem, od = S.build(dn, LV, OH)
    for v in od:
        if v["u"] and v["style"] == "절명":
            v["damage"] *= k
        elif v["style"] == "저격":
            v["damage"] *= m
    for h in names:
        if h in HEALS:
            kk = S.BY[h]
            od.append(dict(id=kk["id"], n=h, style="헌신", u=False, hits=1, stacks=1, damage=0.0, cd=kk["num"]["cd"],
                           motion=kk["num"]["m"] / 1000 + OH))
    return u, mem, od


# ---------- 필드 처치 속도 ----------
def kills(names, order, travel, Ps=HUNT_P, syn=(True, False)):
    S.AMP_HIT.update({k: 0.0 for k in S.AMP_HIT})
    tot = 0
    n = 0
    for P in Ps:
        u, mem, od = _prep(names, P)
        od.sort(key=lambda v: order.index(v["n"]) if v["n"] in order else 99)
        for sy in syn:
            S.SYN = sy
            EV.clear()
            S.run_ev([dict(x) for x in od], mem, T + 200)
            ev = sorted(EV)
            EV.clear()
            for hs in HS:
                H = REF[0] * hs
                hp = H
                sh = 0.0
                k = 0
                for t, d in ev:
                    if t + sh > T:
                        break
                    hp -= d
                    if hp <= 0:
                        k += 1
                        hp = H
                        sh += travel
                tot += k * 60 / T
                n += 1
    S.SYN = True
    return tot / n


def dps_rate(names, order):
    """몹 체력 기준용: 이 트리의 초당 피해(모델 단위)"""
    S.AMP_HIT.update({k: 0.0 for k in S.AMP_HIT})
    u, mem, od = _prep(names, HUNT_P[0])
    od.sort(key=lambda v: order.index(v["n"]) if v["n"] in order else 99)
    EV.clear()
    S.run_ev([dict(x) for x in od], mem, T)
    s = sum(d for t, d in EV if t <= T)
    EV.clear()
    return s / T


def opt_kills(names, start, travel):
    o = start[:]
    b = kills(names, o, travel)
    for _ in range(3):
        mv = False
        for i in range(len(o)):
            for j in range(len(o)):
                if i == j:
                    continue
                t = o[:]
                t.insert(j, t.pop(i))
                v = kills(names, t, travel)
                if v > b + 1e-9:
                    o, b, mv = t, v, True
        if not mv:
            break
    return b, o


def _quick(names, travel, ult):
    if ult is None:
        return -1
    o = sorted(names, key=lambda x: 0 if x in HEALS else -(S.total(S.BY[x]) / S.BY[x]["num"]["cd"])) + [ult]
    return kills(names, o, travel, Ps=HUNT_P[:1], syn=(False,))


def climb(c, seed, travel, cand, fixed=(), melee=False):
    r = random.Random(seed)

    def ult(t):
        if melee:
            if sum(style(x) == "절명" for x in t[:5] if x not in HEALS) < 3:
                return None
            return "암습"
        return S.ult_for(t)

    best = _quick(c, travel, ult(c))
    imp = True
    while imp:
        imp = False
        for i in r.sample(range(len(c)), len(c)):
            if c[i] in fixed:
                continue
            for n in cand:
                if n in c:
                    continue
                t = c[:]
                t[i] = n
                v = _quick(t, travel, ult(t))
                if v > best + 1e-6:
                    best, c, imp = v, t, True
    return best, c


def search(owned, kind, heal, seeds=5, travel=None):
    """kind: 'ranged' (저격·파멸) / 'melee' (절명 3개 이상 + 아무 도술). 결과 [(처치 속도, 칸, 순서)] 내림차순"""
    P = pool(owned)
    heal_n = "생명의 축복" if heal and "생명의 축복" in owned else None
    if heal and not heal_n:
        return []
    melee = kind == "melee"
    tr = travel if travel is not None else (0.7 if melee else 0.3)
    if melee:
        cand = [n for n in P if n != "기습"]
        J = [n for n in cand if style(n) == "절명"]
        if len(J) < 3:
            return []
    else:
        cand = [n for n in P if style(n) in ("저격", "파멸")]
    need = 7 if heal_n else 8
    if len(cand) < need:
        return []
    found = {}
    for s in range(seeds):
        r = random.Random(s)
        if melee:
            b3 = r.sample(J, 3)
            c = b3 + r.sample([n for n in cand if n not in b3], need - 3)
        else:
            c = r.sample(cand, need)
            for _ in range(30):
                if S.ult_for(c):
                    break
                c = r.sample(cand, need)
        c = c + ([heal_n] if heal_n else [])
        v, c = climb(c, s, tr, cand, fixed=(heal_n,) if heal_n else (), melee=melee)
        if v > 0:
            found[tuple(sorted(c))] = c
    rs = []
    for c in found.values():
        u = "암습" if melee else S.ult_for(c)
        if not u:
            continue
        b, o = opt_kills(c, c[:1] + [u] + c[1:], tr)
        rs.append((b, c, o))
    rs.sort(key=lambda x: -x[0])
    return rs


# ---------- 보스 DPS ----------
def boss_score(names, order):
    S.AMP_HIT.clear()
    S.AMP_HIT.update(AMP0)
    tot = 0
    for m, k, c in BOSS_P:
        S.CD_RED = c
        u, mem, od = S.build(names, LV, OH)
        for v in od:
            if v["u"] and v["style"] == "절명":
                v["damage"] *= k
            elif v["style"] == "저격":
                v["damage"] *= m
        od.sort(key=lambda v: order.index(v["n"]) if v["n"] in order else 99)
        for H in (60, 120):
            tot += S.run([dict(x) for x in od], mem, H) * (2 if H == 120 else 1)
    return tot / (3 * len(BOSS_P))


def _boss_quick(names):
    m, k, c = BOSS_P[0]
    S.CD_RED = c
    S.AMP_HIT.clear()
    S.AMP_HIT.update(AMP0)
    u, mem, od = S.build(names, LV, OH)
    for v in od:
        if v["u"] and v["style"] == "절명":
            v["damage"] *= k
        elif v["style"] == "저격":
            v["damage"] *= m
    od.sort(key=lambda a: (not a["u"], -a["damage"] / a["motion"]))
    return S.run(od, mem, 120)


def boss_opt(names, start):
    o = start[:]
    b = boss_score(names, o)
    for _ in range(3):
        mv = False
        for i in range(len(o)):
            for j in range(len(o)):
                if i == j:
                    continue
                t = o[:]
                t.insert(j, t.pop(i))
                v = boss_score(names, t)
                if v > b + 1e-9:
                    o, b, mv = t, v, True
        if not mv:
            break
    return b, o


def boss_search(owned, seeds=6):
    """절명 궁(암습) 보스 트리. 하단 5칸에 절명 3개 이상"""
    cand = [n for n in pool(owned) if n not in ("기습",) and n not in HEALS]
    J = [n for n in cand if style(n) == "절명"]
    if len(J) < 3 or len(cand) < 8:
        return []
    found = {}
    for s in range(seeds):
        r = random.Random(s)
        b3 = r.sample(J, 3)
        c = b3 + r.sample([n for n in cand if n not in b3], 5)
        best = _boss_quick(c)
        imp = True
        while imp:
            imp = False
            for i in r.sample(range(8), 8):
                for n in cand:
                    if n in c:
                        continue
                    t = c[:]
                    t[i] = n
                    if sum(style(x) == "절명" for x in t[:5]) < 3:
                        continue
                    v = _boss_quick(t)
                    if v > best + 1e-6:
                        best, c, imp = v, t, True
        found[tuple(sorted(c))] = c
    rs = []
    for c in found.values():
        b, o = boss_opt(c, ["암습"] + c)
        rs.append((b, c, o))
    rs.sort(key=lambda x: -x[0])
    return rs
