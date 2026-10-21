# 필드 사냥 처치 속도 모델 + 보스 DPS 모델 (시전 시간표는 timeline.py)
# 처치 속도: 피해 이벤트를 몹 체력 H씩 순서대로 적용(남는 피해 버림), 처치마다 이동 시간 추가
import json, os, random
import copy
import timeline as S
import transcend as TR

TGT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "targets.json"), encoding="utf-8"))

S.FORMS_STYLE_ONLY, S.FORMS_PER_CAST, S.STRICT_MAX = False, True, True
AMP0 = dict(S.AMP_HIT)
EV = S.EV

OH = 0.3        # 필드: 도술 사이 딜레이(실측 없음, 대상 찾기·이동 포함 가정)
HEALS = {"생명의 축복", "생명의 흐름"}
# 힐 1개 트리에 넣을 힐(앞쪽 우선): 10/21 패치로 생명의 흐름(공격력 12%×5, 쿨 15초)이 축복(35%, 쿨 20초)보다 초당 회복 2배 이상
HEAL_PICK = ("생명의 흐름", "생명의 축복")


def heal_of(owned):
    return next((h for h in HEAL_PICK if h in owned), None)
LV = {"*": 0}
# (저격 피해 보정, 암습 피해 보정, 검의 형상 쿨 감소): 10/21 패치 뒤 허수아비 실측(절명 신식3 트리 5분 2초, 도술별 횟수·피해 비중)에 맞춤.
#   네 값 모두 도술별 횟수 ±2회, 비중 오차(제곱합) 2.1 아래. tools/check.py '실측 재현'이 이 범위를 지키는지 본다
#   (10/15 실측 기준이던 예전 값 저격 0.9·암습 0.6은 10/21 실측과 비중 오차 9.2)
HUNT_P = [(0.95, 0.65, 6), (1.0, 0.7, 5)]
BOSS_P = [(0.95, 0.65, 6), (1.0, 0.65, 7), (0.95, 0.7, 5), (1.0, 0.7, 5)]
# 보스: 도술 사이 딜레이 0.05초, 평타 0.75초마다 1회(모델 단위 70). 10/21 실측 평타 213회(모델 215회, 0.7초면 229회)
# 필드는 이동과 겹치고 몹이 금방 죽어서 평타를 아직 넣지 않음
OH_BOSS = 0.05
BASIC_BOSS = 70.0
BASIC_I = 0.75
HS = (1.5, 3.0, 5.0)
T = 300
REF = [290.0]
NSLOT = [8]   # 게임에서 열린 도술 칸 수(5~8). analyze가 프로필의 slotCount로 정함


def set_levels(levels):
    LV.clear()
    LV.update({k: int(v or 0) for k, v in levels.items()})
    LV["*"] = 0


_ORIG = {k["n"]: copy.deepcopy(k["num"]) for k in S.D["skills"] if k.get("num")}


def set_steps(steps):
    """돌파 단계 반영: 쿨타임과 피해 계수를 그 사람 기준으로 바꾼다(매번 원본에서 다시 계산)"""
    for k in S.D["skills"]:
        if not k.get("num"):
            continue
        k["num"] = copy.deepcopy(_ORIG[k["n"]])
        st = (steps or {}).get(k["n"], 0)
        if st and k["num"].get("cd"):
            cd, mult = TR.effect(k["n"], st, k["num"]["cd"])
            k["num"]["cd"] = cd
            for d in k["num"].get("dc") or []:
                d["basic_coefficient"] *= mult
            if k["num"].get("total"):
                k["num"]["total"] *= mult
        S.BY[k["n"]] = k


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
    heal_n = heal_of(owned) if heal else None
    if heal and not heal_n:
        return []
    melee = kind == "melee"
    tr = travel if travel is not None else (0.7 if melee else 0.3)
    if melee:
        cand = [n for n in P if n != "기습"]
        J = [n for n in cand if style(n) == "절명"]
        if len(J) < 3:
            return []
    elif kind == "pure":
        cand = [n for n in P if style(n) in ("저격", "파멸") and TGT.get(n, 1) == 1]
    else:
        cand = [n for n in P if style(n) in ("저격", "파멸")]
    need = NSLOT[0] - 1 if heal_n else NSLOT[0]
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
    S.BASIC, S.BASIC_I = BASIC_BOSS, BASIC_I
    tot = 0
    for m, k, c in BOSS_P:
        S.CD_RED = c
        u, mem, od = S.build(names, LV, OH_BOSS)
        for v in od:
            if v["u"] and v["style"] == "절명":
                v["damage"] *= k
            elif v["style"] == "저격":
                v["damage"] *= m
        od.sort(key=lambda v: order.index(v["n"]) if v["n"] in order else 99)
        for H in (60, 120):
            tot += S.run([dict(x) for x in od], mem, H) * (2 if H == 120 else 1)
    S.BASIC = 0.0
    return tot / (3 * len(BOSS_P))


def _boss_quick(names):
    m, k, c = BOSS_P[0]
    S.CD_RED = c
    S.AMP_HIT.clear()
    S.AMP_HIT.update(AMP0)
    u, mem, od = S.build(names, LV, OH_BOSS)
    for v in od:
        if v["u"] and v["style"] == "절명":
            v["damage"] *= k
        elif v["style"] == "저격":
            v["damage"] *= m
    od.sort(key=lambda a: (not a["u"], -a["damage"] / a["motion"]))
    S.BASIC, S.BASIC_I = BASIC_BOSS, BASIC_I
    r = S.run(od, mem, 120)
    S.BASIC = 0.0
    return r


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


def boss_search(owned, seeds=6, st="절명"):
    """스타일 st 궁극기 보스 트리. 하단 5칸에 st 3개 이상"""
    cand = [n for n in pool(owned) if n not in ("기습",) and n not in HEALS]
    J = [n for n in cand if style(n) == st]
    if len(J) < 3 or len(cand) < NSLOT[0]:
        return []
    found = {}
    for s in range(seeds):
        r = random.Random(s)
        b3 = r.sample(J, 3)
        c = b3 + r.sample([n for n in cand if n not in b3], NSLOT[0] - 3)
        best = _boss_quick(c)
        imp = True
        while imp:
            imp = False
            for i in r.sample(range(len(c)), len(c)):
                for n in cand:
                    if n in c:
                        continue
                    t = c[:]
                    t[i] = n
                    if sum(style(x) == st for x in t[:5]) < 3:
                        continue
                    v = _boss_quick(t)
                    if v > best + 1e-6:
                        best, c, imp = v, t, True
        found[tuple(sorted(c))] = c
    rs = []
    ult = S.ULT_OF.get(st)
    for c in found.values():
        b, o = boss_opt(c, ([ult] if ult else []) + c)
        rs.append((b, c, o))
    rs.sort(key=lambda x: -x[0])
    return rs


def style_hunt(owned, st, seeds=4, heal=False):
    """스타일 st 궁극기 필드 사냥 트리(하단 st 3개 이상). 근거리 0.7초·원거리 0.3초·그 외 0.5초 이동"""
    P = [n for n in pool(owned) if n != "기습" and n not in HEALS]
    J = [n for n in P if style(n) == st]
    ult = S.ULT_OF.get(st)
    need = NSLOT[0] - 1 if heal else NSLOT[0]
    if len(J) < 3 or len(P) < need or not ult:
        return []
    heal_n = heal_of(owned) if heal else None
    if heal and not heal_n:
        return []
    kind = {"절명": "근", "연타": "근", "강타": "근", "척살": "근", "저격": "원", "주술": "원", "파멸": "원"}.get(st)
    tr = 0.7 if kind == "근" else (0.3 if kind == "원" else 0.5)

    def ok(t):
        return sum(style(x) == st for x in t[:5] if x not in HEALS) >= 3

    found = {}
    for s0 in range(seeds):
        r = random.Random(s0)
        b3 = r.sample(J, 3)
        c = b3 + r.sample([n for n in P if n not in b3], need - 3) + ([heal_n] if heal_n else [])
        best = kills(c, sorted(c, key=lambda x: 0 if x in HEALS else -(S.total(S.BY[x]) / S.BY[x]["num"]["cd"])) + [ult], tr, Ps=HUNT_P[:1], syn=(False,))
        imp = True
        while imp:
            imp = False
            for i in r.sample(range(len(c)), len(c)):
                if c[i] == heal_n:
                    continue
                for n in P:
                    if n in c:
                        continue
                    t = c[:]
                    t[i] = n
                    if not ok(t):
                        continue
                    v = kills(t, sorted(t, key=lambda x: 0 if x in HEALS else -(S.total(S.BY[x]) / S.BY[x]["num"]["cd"])) + [ult], tr, Ps=HUNT_P[:1], syn=(False,))
                    if v > best + 1e-6:
                        best, c, imp = v, t, True
        found[tuple(sorted(c))] = c
    rs = []
    for c in found.values():
        b, o = opt_kills(c, c[:1] + [ult] + c[1:], tr)
        rs.append((b, c, o, tr))
    rs.sort(key=lambda x: -x[0])
    return rs
