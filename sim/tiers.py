# 등급(생존·믹스·딜)별 계산 1위: 딜 손해 한도 안에서 유지력(초당 회복·보호막)이 가장 큰 조합
#   딜 = 유지 도술 0개 중 딜 1위 / 믹스 = 1개, 딜 카드 대비 −5% 안(없으면 1개 중 딜 1위) / 생존 = 아래. 후보(Cand) = {score, order, ult, susN, sus, ...호출자가 붙인 값}
#   생존 카드는 계산 트리 2개(10/22 사용자 결정): 생존 우선 = 유지 2개 이상 후보 중 그 딜 1위 대비 −10% 안에서 유지력 최대,
#   딜 우선(생존2) = 유지 2개 이상 중 딜 1위(생존 우선과 같으면 없음)
import sustain as SU

HEALS = {"생명의 축복", "생명의 흐름"}
WIN = {"믹스": 0.95, "생존": 0.90}
KEEP = {"영혼 소용돌이"}   # 칸 바꾸기에서 빼지 않는 도술(몰이 모으기)


def add_sustain(order, ult, skill, score, ok):
    """유지 도술 하나를 넣은 가장 좋은 배치 (점수, 순서). 힐은 기존 힐 바로 뒤(맨 앞쪽), 그 밖은 바꾼 칸 자리에.
    궁극기·영혼 소용돌이·이미 든 유지 도술은 빼지 않는다"""
    if skill in order:
        return None
    lead = [x for x in order if x in HEALS]
    rest = [x for x in order if x not in HEALS]
    keep = {ult} | KEEP | set(SU.active(order))
    best = None
    for i, x in enumerate(rest):
        if x in keep:
            continue
        if skill in HEALS:
            t = lead + [skill] + rest[:i] + rest[i + 1:]
        else:
            t = lead + rest[:i] + [skill] + rest[i + 1:]
        if not ok(t):
            continue
        v = score(t)
        if not best or v > best[0]:
            best = (v, t)
    return best


def expand(seeds, owned, score, ok, make, top=5):
    """씨앗 + 유지 0개 1위에 유지 도술 1개씩 + 유지 1개 상위에 1개 더 + 유지 2개 상위에 1개 더(힐 2 + 보호막 포함).
    score(부모, 순서)·ok(부모, 순서)는 부모 후보의 조건(이동 시간 등)으로 계산, make(점수, 순서, 부모) → 새 후보"""
    out, seen = [], set()

    def put(c):
        k = tuple(c["order"])
        if k not in seen:
            seen.add(k)
            out.append(c)

    for c in seeds:
        put(c)
    if not out:
        return out
    sus = [n for n in SU.UNCOND if n in owned]

    def grow(froms):
        for c in froms:
            for s in sus:
                r = add_sustain(c["order"], c["ult"], s, lambda o: score(c, o), lambda o: ok(c, o))
                if r:
                    put(make(r[0], r[1], c))

    zero = [c for c in out if c["susN"] == 0]
    grow([max(zero or out, key=lambda c: c["score"])])
    for n in (1, 2):
        grow(sorted((c for c in out if c["susN"] == n), key=lambda c: -c["score"])[:top])
    return out


def pick_tiers(cands):
    """등급별 계산 1위. 고른 후보에는 딜 카드 대비 dmgPct(%)를 붙인다(딜 후보가 없으면 전체 1위 대비)"""
    deal = max((c for c in cands if c["susN"] == 0), key=lambda c: c["score"], default=None)
    ref = deal["score"] if deal else max((c["score"] for c in cands), default=None)
    res = {"딜": deal}
    pool = [c for c in cands if c["susN"] == 1]
    inwin = [c for c in pool if c["score"] >= ref * WIN["믹스"]]
    if inwin:
        res["믹스"] = max(inwin, key=lambda c: (c["sus"], c["score"]))
    else:
        res["믹스"] = max(pool, key=lambda c: c["score"], default=None)
    pool = [c for c in cands if c["susN"] >= 2]
    top = max(pool, key=lambda c: c["score"], default=None)
    res["생존"] = top and max((c for c in pool if c["score"] >= top["score"] * WIN["생존"]), key=lambda c: (c["sus"], c["score"]))
    res["생존2"] = top if top and top["order"] != res["생존"]["order"] else None
    for tier, c in res.items():
        if c:
            res[tier] = dict(c, dmgPct=(c["score"] / ref - 1) * 100)
    return res
