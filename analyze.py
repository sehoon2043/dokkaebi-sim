# 도사 수첩 자동 분석: 저장 서버(Vercel)에서 새로 저장된 프로필을 받아 추천 트리를 계산해 돌려준다(진행률도 서버에 보고)
#   python analyze.py                 → DOSA_URL·DOSA_KEY 환경변수로 대기 중인 프로필 전부 처리
#   python analyze.py --local p.json  → 로컬 프로필 파일 하나 계산해서 결과 출력(테스트용)
import json, os, re, sys, time, random, urllib.request, urllib.parse
from concurrent.futures import ProcessPoolExecutor, as_completed
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim"))
import field as F
import mob as M
import transcend as TR
import explain as EX
import verify as VF

TODAY = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 9 * 3600))
STYLE_ORDER = ["절명", "연타", "강타", "척살", "저격", "주술", "파멸", "강인", "기동", "헌신", "기만", "제압"]
WORKERS = max(1, min(8, os.cpu_count() or 1))
PROG = [None]   # 진행률 보고 함수 (pct, 단계 이름)


def progress(pct, stage):
    if PROG[0]:
        PROG[0](pct, stage)


def arrange(order, ult):
    """칸 배치: 사용 순서대로, 하단 5칸에 궁극기 스타일 3개 이상"""
    seq = [n for n in order if n != ult]
    bot, f = seq[:5], seq[5:]
    st = F.style(ult)
    while sum(F.style(n) == st for n in bot if n not in F.HEALS) < 3:
        take = next(n for n in f if n not in F.HEALS and F.style(n) == st)
        give = [n for n in bot if n in F.HEALS or F.style(n) != st][-1]
        bot[bot.index(give)] = take
        f[f.index(take)] = give
        bot.sort(key=seq.index)
        f.sort(key=seq.index)
    return bot + f


# ---------- 몰이 ----------
YT_AOE = ["연쇄 타격", "난타", "회전 난격"]


def mob_search(owned, heals):
    """궁극기(연타·파멸·강타·주술·기만)마다 그 스타일 3개를 넣은 몰이 트리를 찾아 가장 좋은 것"""
    hl = [h for h in ("생명의 축복", "생명의 흐름")[:heals] if h in owned]
    if len(hl) < heals:
        return None
    aoe = [n for n in M.K if n in owned and n in M.AOE and n not in M.HEALS and M.K[n]["dmg"] > 0 and not M.K[n].get("u")]
    rs = []
    for ult, st in M.ULT_MODE.items():   # 궁극기는 보유 목록에 없음(스타일 3개면 자동 등록)
        r = _mob_one(owned, hl, aoe, ult, st)
        if r:
            rs.append(r)
    return max(rs, key=lambda x: x[0]) if rs else None


def _mob_one(owned, hl, aoe, ult, st):
    val = lambda n: M.K[n]["dmg"] * min(5, M.TGT.get(n, 1)) / M.K[n]["cd"]
    mine = [n for n in M.K if n in owned and M.K[n]["style"] == st and n not in M.HEALS and M.K[n]["dmg"] > 0 and not M.K[n].get("u")]
    if len(mine) < 3:
        return None
    core = sorted(mine, key=lambda n: (n not in M.AOE, -val(n)))[:3]
    swirl = ["영혼 소용돌이"] if "영혼 소용돌이" in owned and "영혼 소용돌이" not in core else []
    fixed = core + swirl + hl
    free = F.NSLOT[0] - len(fixed)
    cand = [n for n in aoe if n not in fixed]
    if free < 0 or len(cand) < free:
        return None
    pick = sorted(cand, key=lambda n: -val(n))[:free]

    def order_of(sl):
        first = [x for x in sl if x == "영혼 소용돌이"]
        rest = sorted([x for x in sl if x not in first and x not in hl], key=lambda n: -val(n))
        o = first + rest
        o.insert(min(6, len(o)), ult)
        return o + hl

    best = M.w(order_of(fixed + pick))
    sl = fixed + pick
    imp = True
    while imp:
        imp = False
        for i in list(range(3)) + list(range(len(fixed), F.NSLOT[0])):
            for n in (mine if i < 3 else cand):
                if n in sl:
                    continue
                t = sl[:]
                t[i] = n
                v = M.w(order_of(t))
                if v > best + 1e-6:
                    best, sl, imp = v, t, True
    b, o = M.opt(order_of(sl), 200)
    return b, o, ult


def mob_add_heal(prev, owned, heal):
    """몰이 트리에서 한 칸만 힐로 바꾼다(나머지 도술·순서는 그대로). 소용돌이·궁극기·기존 힐은 유지"""
    if not prev or heal not in owned:
        return None
    _, o, ult = prev
    st = F.style(ult)
    best = None
    for i, x in enumerate(o):
        if x == ult or x in M.HEALS or x == "영혼 소용돌이":
            continue
        t = o[:]
        t[i] = heal
        if sum(F.style(k) == st for k in t if k != ult and k not in M.HEALS) < 3 or not M.valid_order(t):
            continue
        v = M.w(t)
        if not best or v > best[0]:
            best = (v, t, ult)
    return best


# ---------- 커뮤니티 덱 ----------
BUILDS = []
NEAR = {"절명", "연타", "강타", "척살"}


def load_builds(n=5):
    out = []
    for page in (1, 2):
        try:
            req = urllib.request.Request(f"https://kkaebigg.com/guilds/api/deck-builds?sort=popular&page={page}",
                                         headers={"Accept": "application/json", "User-Agent": "dokkaebi-dosa-analyzer"})
            d = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
        except Exception as e:
            print("커뮤니티 덱 받기 실패", type(e).__name__)
            break
        out += d.get("items") or []
        if page >= (d.get("pages") or 1):
            break
    out = [b for b in out if b.get("slots") and b.get("ult")]
    out.sort(key=lambda b: -(b.get("likes") or 0))
    return out[:n]


def community(bd, owned, ref):
    names = [x["name"] for x in bd["slots"] if x.get("name")]
    ult = bd["ult"]["name"]
    order = [x["name"] for x in (bd.get("order") or bd["slots"]) if x.get("name") in names]
    order.insert(max(0, min(len(order), int(bd.get("ult_at") or 0))), ult)
    known = [n for n in names if n in F.S.BY]
    missing = [n for n in names if n not in owned]
    near = sum(F.style(n) in NEAR for n in known) >= 4
    tr = 0.7 if near else 0.3
    lines, cmp = [], {}
    mo = [x for x in order if x in M.K or x in ("폭주", "대폭발")]
    if mo:
        v = M.w(mo)
        cmp["mob"] = v
        lines.append(f"몰이 점수 {v:.0f}" + (f" (내 몰이 대비 {(v / ref['mob'] - 1) * 100:+.0f}%)" if ref["mob"] else ""))
    fo = [x for x in order if x in F.S.BY]
    if known:
        v = F.kills(known, fo, tr)
        cmp["field"] = v
        lines.append(f"필드 1분에 약 {v:.1f}마리 (이동 {tr}초)" + (f" (내 평범 대비 {(v / ref['field'] - 1) * 100:+.0f}%)" if ref["field"] else ""))
        v = F.boss_score(known, fo)
        cmp["boss"] = v
        lines.append("보스 점수" + (f" 내 최고 보스 트리 대비 {(v / ref['boss'] - 1) * 100:+.0f}%" if ref["boss"] else f" {v:.0f}"))
    best = max(((k, cmp[k] / ref[k]) for k in cmp if ref.get(k)), key=lambda x: x[1], default=None)
    label = {"mob": "몰이", "field": "필드 사냥", "boss": "보스"}
    pts = []
    if best:
        k, r = best
        pts.append(f"{label[k]}용 · 내 추천보다 약 {abs(r - 1) * 100:.0f}% " + ("좋음" if r > 1 else "낮음") if abs(r - 1) >= 0.01 else f"{label[k]}용 · 내 추천과 비슷")
    if missing:
        pts.append("안 배운 도술: " + ", ".join(missing) + " (배웠다고 치고 계산)")
    if ult not in M.ULT_MODE and ult != "연속 쇄도":
        pts.append(f"궁극기 {ult}의 신식·이동 효과는 몰이 계산에 일부만 반영")
    tail = ["작성 " + (bd.get("author") or {}).get("name", "익명") + f" · 추천 {bd.get('likes', 0)}"]
    nm = bd.get("name") or "이름 없는 덱"
    tab = nm if len(nm) <= 14 else nm[:13] + "…"
    t = {"id": f"comm_{bd.get('id')}", "tab": tab, "sub": nm, "slots": names, "ult": ult, "order": order,
         "stat": " · ".join(lines), "points": pts + EX.links(order) + tail, "alt": [], "warn": bool(missing)}
    return t


# ---------- 배우면 좋은 도술 ----------
def _all_damage_skills():
    return [k["n"] for k in F.S.D["skills"] if not k["u"] and k.get("num") and F.S.total(k) > 0 and k["num"]["cd"]
            and k["n"] not in ("은신", "기습") and k["n"] not in F.HEALS]


def suggest(kind, order, ult, owned, tr=0.3):
    """안 배운 도술 하나를 넣었을 때 3% 넘게 좋아지는 것(최대 2개)"""
    slots = [x for x in order if x != ult]
    ust = F.style(ult) if ult in F.S.BY else None
    heals = [x for x in slots if x in F.HEALS]
    if kind == "mob":
        val = lambda n: M.K[n]["dmg"] * min(5, M.TGT.get(n, 1)) / M.K[n]["cd"] if n in M.K else 0
        pool = [n for n in M.K if n not in owned and n in M.AOE and n not in M.HEALS and M.K[n]["dmg"] > 0 and not F.S.BY[n]["u"]]
        q = M.quick
    else:
        val = lambda n: F.S.total(F.S.BY[n]) / F.S.BY[n]["num"]["cd"]
        pool = [n for n in _all_damage_skills() if n not in owned]
        # 칸은 arrange로 놓아야 하단 5칸에 궁극기 스타일 3개가 들어가 궁극기가 계산에 들어간다
        lay = (lambda o: arrange(o, ult)) if ust else (lambda o: [x for x in o if x != ult])
        if kind == "boss":
            q = lambda o: F.boss_score(lay(o), o)
        else:
            q = lambda o: F.kills(lay(o), o, tr, Ps=F.HUNT_P[:1], syn=(False,))
    pool = sorted(pool, key=lambda n: -val(n))[:12]
    base = q(order)
    if not base:
        return []
    best = {}
    for i, x in enumerate(order):
        if x == ult or x in heals:
            continue
        for n in pool:
            o2 = order[:]
            o2[i] = n
            if ust and sum(F.style(y) == ust for y in o2 if y != ult and y not in F.HEALS) < 3:
                continue
            g = q(o2) / base - 1
            if g > best.get(n, (0, ""))[0]:
                best[n] = (g, x)
    top = sorted(((g, n, x) for n, (g, x) in best.items() if g > 0.03), reverse=True)[:2]
    return [f"배우면 좋음: {n} ({x} 대신, 약 +{g * 100:.0f}%)" for g, n, x in top]


# ---------- 탐색 보강 ----------
def top(tid, rs, owned, kind, tr=None):
    """탐색 1위를 한 칸씩 바꿔 보며 더 좋은 조합이 있으면 바꾼다. (점수, 칸, 순서, 궁극기)"""
    b, c, o = rs[0][:3]
    u = next((x for x in o if F.S.BY[x]["u"]), None) or F.S.ult_for(c)
    if kind == "boss":
        reopt = lambda t: F.boss_opt(arrange(t, u), t)
    else:
        reopt = lambda t: F.opt_kills(arrange(t, u), t, tr)
    try:
        r = VF.polish(tid, owned, o, u, arrange, reopt)
    except Exception as e:
        print("탐색 보강 실패", tid, type(e).__name__)
        r = None
    if r and r[2]:
        b, o = r[0], r[1]
        c = arrange(o, u)
    return b, c, o, u


def _setup(levels, steps, ref, nslot=8):
    F.NSLOT[0] = nslot
    F.set_levels(levels)
    F.set_steps(steps)
    M.setup(levels, steps)
    F.REF[0] = ref


def _verify_one(t, owned, parent):
    try:
        return VF.check(t, owned, arrange, parent)
    except Exception as e:
        print("검증 실패", t["id"], type(e).__name__, e)
        return None


def _job(job, owned):
    """탐색 작업 하나(다른 작업과 독립). 결과는 프로세스 사이로 넘길 수 있는 값만"""
    kind = job[0]
    if kind == "mob":
        r = mob_search(owned, 0)
        if r:
            b, o, ult = r
            p = VF.polish("mob", owned, o, ult, arrange, lambda t: M.opt(t, 200))
            if p and p[2]:
                r = (p[0], p[1], ult)
        r1 = mob_add_heal(r, owned, "생명의 흐름")   # 10/21: 흐름 회복량이 축복의 2배 이상
        r2 = mob_add_heal(r1, owned, "생명의 축복")
        return [r, r1, r2]
    if kind == "rng":
        rng = F.search(owned, "ranged", False, seeds=4)
        return ([(x[0], x[1]) for x in rng[:2]], top("single", rng, owned, "field", 0.3) if rng else None)
    if kind in ("pure", "pureh", "rh"):
        k, heal, seeds, tid = {"pure": ("pure", False, 4, "pure"), "pureh": ("pure", True, 3, "pureh"), "rh": ("ranged", True, 4, "singleh")}[kind]
        rs = F.search(owned, k, heal, seeds=seeds)
        return top(tid, rs, owned, "field", 0.3) if rs else None
    if kind == "melee":
        heal = job[1]
        me = F.search(owned, "melee", heal, seeds=4 if not heal else 3)
        if not me:
            return None
        b0, c, o, _ = top("jhunt_h" if heal else "jhunt", me, owned, "field", 0.7)
        return (b0, c, o, F.kills(c, o, 0.4), F.kills(c, o, 1.0))
    if kind == "boss":
        bs = F.boss_search(owned, seeds=5)
        if not bs:
            return None
        b, c, o, _ = top("boss", bs, owned, "boss")
        return (b, c, o, (bs[1][0], bs[1][1]) if len(bs) > 1 else None)
    if kind == "boss_st":
        st = job[1]
        bs2 = F.boss_search(owned, seeds=3, st=st)
        if not bs2:
            return None
        b, c, o, _ = top("boss_" + st, bs2, owned, "boss")
        return (b, c, o, F.S.ULT_OF.get(st))
    if kind == "hunt_st":
        st = job[1]
        hs = F.style_hunt(owned, st, seeds=3)
        if not hs:
            return None
        tr_ = hs[0][3]
        b, c, o, _ = top("hunt_" + st, hs, owned, "field", tr_)
        return (b, c, o, F.S.ULT_OF.get(st), tr_)
    raise ValueError(job)


def _job_safe(job, owned):
    try:
        return _job(job, owned)
    except Exception as e:
        print("탐색 실패", job, type(e).__name__, e)
        return None


def run_jobs(jobs, owned, ctx, p0, p1):
    """탐색 작업들을 여러 프로세스로 나눠 실행. 오래 걸리는 작업부터 넣는다"""
    weight = {"rng": 5, "melee": 4, "rh": 3, "boss": 3, "hunt_st": 3, "boss_st": 2, "pure": 2, "pureh": 1, "mob": 1}
    order = sorted(jobs, key=lambda j: -weight.get(j[0], 1))
    out = {}
    if WORKERS > 1:
        with ProcessPoolExecutor(WORKERS, initializer=_setup, initargs=ctx) as ex:
            futs = {ex.submit(_job_safe, j, owned): j for j in order}
            for i, f in enumerate(as_completed(futs), 1):
                out[futs[f]] = f.result()
                progress(p0 + (p1 - p0) * i / len(jobs), "몰이·필드 사냥·보스 트리")
    else:
        for i, j in enumerate(order, 1):
            out[j] = _job_safe(j, owned)
            progress(p0 + (p1 - p0) * i / len(jobs), "몰이·필드 사냥·보스 트리")
    return out


def verify_all(trees, owned, ctx, p0=55, p1=97):
    """트리마다 검증(한 칸 바꾼 조합 비교 + 가정 흔들기) 결과를 붙인다. 트리끼리 독립이라 여러 프로세스로 나눠 계산"""
    by = {t["id"]: t for t in trees}
    jobs = []
    for t in trees:
        parent = None
        if t["id"] == "mobheal" and "mob" in by:
            parent = by["mob"]["order"]
        elif t["id"] == "mobheal2" and "mobheal" in by:
            parent = by["mobheal"]["order"]
        jobs.append((t, parent))
    n = len(jobs)
    if WORKERS > 1 and n > 1:
        with ProcessPoolExecutor(WORKERS, initializer=_setup, initargs=ctx) as ex:
            futs = {ex.submit(_verify_one, t, owned, parent): t for t, parent in jobs}
            for i, f in enumerate(as_completed(futs), 1):
                v = f.result()
                if v:
                    futs[f]["verify"] = v
                progress(p0 + (p1 - p0) * i / n, "추천 트리 검증")
    else:
        for i, (t, parent) in enumerate(jobs, 1):
            v = _verify_one(t, owned, parent)
            if v:
                t["verify"] = v
            progress(p0 + (p1 - p0) * i / n, "추천 트리 검증")


# ---------- 결과 조립 ----------
def tree(tid, tab, sub, order, ult, stat, points, alt=None):
    return {"id": tid, "tab": tab, "sub": sub, "slots": arrange(order, ult), "ult": ult, "order": order,
            "stat": stat, "points": EX.points(order, ult, points), "alt": alt or [], "warn": False}


def mark_best(trees):
    """분류(몰이·필드 사냥·보스)마다 가장 좋은 트리 하나에 best 표시. 몰이는 힐 없는 몰이, 나머지는 점수(_v) 1위"""
    mob = next((t for t in trees if t["id"] == "mob"), None) or next((t for t in trees if t["id"].startswith("mob")), None)
    field = [t for t in trees if "_v" in t and (t["id"] in ("pure", "single", "jhunt") or t["id"].startswith("hunt_"))]
    boss = [t for t in trees if "_v" in t and (t["id"] == "boss" or t["id"].startswith("boss_"))]
    for t in [mob, max(field, key=lambda x: x["_v"], default=None), max(boss, key=lambda x: x["_v"], default=None)]:
        if t:
            t["best"] = True
    for t in trees:
        t.pop("_v", None)


def analyze(data):
    levels = {k: int(v or 0) for k, v in (data.get("levels") or {}).items() if str(v).strip() != ""}
    owned_map = data.get("owned") or {}
    owned = set(owned_map.keys())
    steps = TR.steps_of(owned_map)
    try:
        F.NSLOT[0] = max(5, min(8, int(data.get("slotCount") or 8)))
    except (TypeError, ValueError):
        F.NSLOT[0] = 8
    F.set_levels(levels)
    F.set_steps(steps)
    M.setup(levels, steps)
    trees = []
    notes = []
    progress(2, "몰이 트리")
    ref = {"mob": None, "field": None, "boss": None}
    # 필드 사냥 몹 체력 기준(REF) = 이 사람의 평범(원거리) 트리 초당 피해. 이것만 먼저 정하고 나머지 탐색은 동시에
    F.REF[0] = 290.0
    rng0 = F.search(owned, "ranged", False, seeds=4)
    if rng0:
        F.REF[0] = F.dps_rate(rng0[0][1], rng0[0][2])
    progress(5, "몰이·필드 사냥·보스 트리")
    P = F.pool(owned)
    cnt = {st: sum(F.style(n) == st for n in P if n not in F.HEALS) for st in STYLE_ORDER}
    sts = sorted([x for x in STYLE_ORDER if cnt[x] >= 3], key=lambda x: -cnt[x])
    jobs = [("mob",), ("rng",), ("pure",), ("pureh",), ("rh",), ("melee", False), ("melee", True), ("boss",)]
    jobs += [("boss_st", st) for st in sts if st != "절명"] + [("hunt_st", st) for st in sts if st not in ("절명", "저격", "파멸")]
    R = run_jobs(jobs, owned, (levels, steps, F.REF[0], F.NSLOT[0]), 5, 50)

    # 몰이 0/1/2힐
    for h, tid, tab in ((0, "mob", "몰이"), (1, "mobheal", "몰이+힐"), (2, "mobheal2", "몰이+2힐")):
        r = (R[("mob",)] or [None, None, None])[h]
        if r and h == 0:
            ref["mob"] = r[0]
        if not r:
            if h == 0:
                notes.append("몰이: 광역 도술이 부족해 계산하지 못했습니다(한 스타일 도술 3개와 광역 도술이 필요).")
            continue
        b, o, ult = r
        use = ("몹이 한곳에 모이는 곳(엽전 비경 등)에서 가장 빠른 몰이입니다.",
               f"물약을 먹을 때. 몰이에서 한 칸만 {EX.josa('생명의 흐름', '으로/로')} 바꿨습니다.",
               f"물약이 많이 들 때. 몰이+힐에서 한 칸만 {EX.josa('생명의 축복', '으로/로')} 바꿨습니다.")[h]
        pts = [use]
        if not h:
            pts.append(f"하단 {F.style(ult)} 3개 → 궁극기 {ult}")
            if "영혼 소용돌이" not in o:
                pts.append("영혼 소용돌이를 배우면 몹 모으기가 훨씬 편해집니다.")
            if M.gathered(o):
                pts.append("공간 결계는 몹을 모아 줘서 넣었습니다(엽전 비경 실측 약 +6.5%).")
        trees.append(tree(tid, tab, f"힐 {h}개 · 궁극기 {ult}" if h else f"힐 없음 · 궁극기 {ult}", o, ult,
                          "몹 5마리가 뭉쳐 있는 조건" + (" · 공간 결계로 몹이 더 잘 모임(실측 보정)" if M.gathered(o) else ""), pts))
    rng, single_top = R[("rng",)] or ([], None)
    base = single_top[0] if single_top else None

    def rel(v, ref, name):
        if not ref:
            return None
        d = (v / ref - 1) * 100
        return f"{name}보다 약 {abs(d):.0f}% " + ("빠름" if d > 0 else "느림") if abs(d) >= 1 else f"{name}과 비슷"

    def stat(*parts):
        return " · ".join(x for x in parts if x)

    pure_b = None
    if R[("pure",)]:
        b0, c, o, u = R[("pure",)]
        pure_b = b0
        trees.append(tree("pure", "완전 단일", f"단일 대상 도술만 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리 (몹 1~5초 처치, 몹 사이 이동 0.3초)", rel(b0, base, "평범 사냥")),
                          ["몹이 띄엄띄엄 있거나 옆 몹을 건드리기 싫을 때. 광역 도술 없이 한 마리씩 잡습니다."]))
        trees[-1]["_v"] = b0
    if R[("pureh",)]:
        b0, c, o, u = R[("pureh",)]
        trees.append(tree("pureh", "완전 단일+힐", f"단일 대상 도술만 + 생명의 축복 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리", rel(b0, pure_b, "완전 단일")), ["완전 단일에서 물약이 많이 들 때."]))
    if single_top:
        b0, c, o, u = single_top
        trees.append(tree("single", "평범", f"한 마리씩 잡지만 광역 도술 섞음 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리 (몹 1~5초 처치, 몹 사이 이동 0.3초)", rel(b0, pure_b, "완전 단일")),
                          ["일반 필드 사냥의 기본. 광역 도술이 섞여 몹이 붙어 있으면 덤으로 더 잡힙니다.", f"하단 {F.style(u)} 3개 → 궁극기 {u}"],
                          [f"2위({(rng[1][0] / b0 - 1) * 100:+.1f}%): {', '.join(rng[1][1])}"] if len(rng) > 1 and sorted(rng[1][1]) != sorted(c) else []))
        trees[-1]["_v"] = b0
    if R[("rh",)]:
        b0, c, o, u = R[("rh",)]
        trees.append(tree("singleh", "평범+힐", f"평범 사냥 + 생명의 축복 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리", rel(b0, base, "평범 사냥")), ["평범 사냥에서 물약이 많이 들 때. 원거리라 근접보다 덜 맞습니다."]))
    for heal, tid, tab in ((False, "jhunt", "절명"), (True, "jhunt_h", "절명+힐")):
        r = R[("melee", heal)]
        if not r:
            continue
        b0, c, o, k04, k10 = r
        trees.append(tree(tid, tab, "근접 필드 사냥" + (", 힐 1개" if heal else ", 힐 없음") + " · 궁극기 암습", o, "암습",
                          stat(f"1분에 약 {b0:.1f}마리 (몹 사이 이동 0.7초)", f"촘촘하면(0.4초) 약 {k04:.1f}마리", f"흩어져 있으면(1초) 약 {k10:.1f}마리"),
                          ["몹이 촘촘한 곳에서 빠름. 흩어져 있으면 평범이 낫습니다." if not heal else "근접으로 해야 할 때만. 보통은 평범+힐이 더 빠르고 덜 맞습니다.",
                           "하단 절명 3개 → 궁극기 암습"]))
        if not heal:
            trees[-1]["_v"] = b0
    ref["field"] = base
    boss_b = None
    if R[("boss",)]:
        b, c, o, second = R[("boss",)]
        ref["boss"] = boss_b = b
        trees.append(tree("boss", "절명 보스", "절명 + 저격, 기습 안 씀 · 궁극기 암습", o, "암습", "보스·필드보스·레이드용",
                          ["하단 절명 3개 → 궁극기 암습"],
                          [f"2위({(second[0] / b - 1) * 100:+.1f}%): {', '.join(second[1])}"] if second and sorted(second[1]) != sorted(c) else []))
        trees[-1]["_v"] = b
    # 주력 스타일별 트리: 공격 도술 3개 이상 배운 스타일마다 보스(궁극기 그 스타일) · 사냥
    for st in sts:
        r = R.get(("boss_st", st))
        if r:
            b, c, o, u = r
            cmp_ = ""
            if boss_b:
                d = (b / boss_b - 1) * 100
                cmp_ = " · 절명 보스와 비슷" if abs(d) < 1 else f" · 절명 보스보다 약 {abs(d):.0f}% " + ("높음" if d > 0 else "낮음")
            ref["boss"] = max(ref["boss"] or 0, b)
            trees.append(tree("boss_" + st, st + " 보스", f"{st} 위주 · 궁극기 {u}", o, u, "보스·필드보스·레이드용" + cmp_,
                              [f"하단 {st} 3개 → 궁극기 {u}"]))
            trees[-1]["_v"] = b
        r = R.get(("hunt_st", st))
        if r:
            b, c, o, u, tr_ = r
            trees.append(tree("hunt_" + st, st + " 사냥", f"{st} 위주 필드 사냥 · 궁극기 {u}", o, u,
                              stat(f"1분에 약 {b:.1f}마리 (몹 사이 이동 {tr_}초)", rel(b, base, "평범 사냥")),
                              [f"하단 {st} 3개 → 궁극기 {u}"]))
            trees[-1]["_v"] = b
    progress(52, "더 좋은 도술 찾기")
    # 주요 트리: 안 배운 도술 중 넣으면 좋은 것
    for t in trees:
        kind = {"mob": "mob", "single": "field", "jhunt": "field", "boss": "boss"}.get(t["id"])
        if not kind:
            continue
        try:
            sg = suggest(kind, t["order"], t["ult"], owned, 0.7 if t["id"] == "jhunt" else 0.3)
        except Exception:
            sg = []
        if sg:
            t["points"] = t["points"] + sg[:1]
    mark_best(trees)
    progress(55, "추천 트리 검증")
    verify_all(trees, owned, (levels, steps, F.REF[0], F.NSLOT[0]), 55, 97)
    progress(97, "커뮤니티 덱 비교")
    # 커뮤니티 덱(외부 덱 게시판 인기순) — 이 사람 강화·각성 기준 점수와 내 추천 대비
    if not BUILDS:
        notes.append("커뮤니티 덱을 불러오지 못해 이번 계산에서는 빠졌어요.")
    for bd in BUILDS:
        try:
            trees.append(community(bd, owned, ref))
        except Exception as e:
            notes.append(f"커뮤니티 덱 '{bd.get('name', '')[:20]}' 계산 실패({type(e).__name__})")
    lv = " · ".join(f"{s} {levels[s]}" for s in STYLE_ORDER if levels.get(s))
    br = f" · 각성 반영 {len(steps)}개" if steps else ""
    return {"updated": TODAY, "basis": (lv or "강화 정보 없음") + br + f", 도술 {F.NSLOT[0]}칸", "trees": trees, "notes": notes}


# ---------- Apps Script 통신 ----------
def call(url, params=None, body=None):
    if body is None:
        req = urllib.request.Request(url + "?" + urllib.parse.urlencode(params))
    else:
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "text/plain;charset=utf-8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--local":
        d = json.load(open(sys.argv[2], encoding="utf-8"))
        BUILDS[:] = load_builds()
        t0 = time.time()
        res = analyze(d.get("data", d))
        print(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"# {time.time() - t0:.0f}초", file=sys.stderr)
        return
    url = os.environ["DOSA_URL"]
    key = os.environ["DOSA_KEY"]
    # GitHub Actions: --plan 으로 대기 프로필 목록(닉네임 대신 짧은 해시)을 만들고, --one 해시 로 프로필마다 따로(동시에) 계산
    if len(sys.argv) > 1 and sys.argv[1] == "--plan":
        r = call(url, {"a": "pending", "key": key})
        if not r.get("ok"):
            print("pending 실패", r.get("err"), file=sys.stderr)
            sys.exit(1)
        for i, x in enumerate(r["list"]):
            reporter(url, key, x)(0, "곧 시작")
        print("ids=" + json.dumps([tag(x["nick"]) for x in r["list"]]))
        return
    if len(sys.argv) > 2 and sys.argv[1] == "--one":
        if not re.fullmatch(r"[0-9a-f]{10}", sys.argv[2]):
            print("잘못된 해시", file=sys.stderr)
            sys.exit(1)
        r = call(url, {"a": "pending", "key": key})
        todo = [x for x in r.get("list", []) if tag(x["nick"]) == sys.argv[2]]
        print("대기", len(todo), "· 병렬", WORKERS)
        if todo:
            BUILDS[:] = load_builds()
            run_list(todo, url, key, {})
        return
    BUILDS[:] = load_builds()
    print("커뮤니티 덱", len(BUILDS), "· 병렬", WORKERS)
    done = {}
    for rnd in range(6):   # 분석 중에 새로 저장된 것도 이어서 처리
        r = call(url, {"a": "pending", "key": key})
        if not r.get("ok"):
            print("pending 실패", r.get("err"))
            sys.exit(1)
        todo = [p for p in r["list"] if done.get(p["nick"]) != str(p["updatedAt"])]
        print("대기", len(todo))
        if not todo:
            break
        run_list(todo, url, key, done)


def tag(nick):
    """실행 기록(공개)에 닉네임 대신 남기는 짧은 해시"""
    import hashlib
    return hashlib.sha1(nick.encode("utf-8")).hexdigest()[:10]


def reporter(url, key, p):
    """진행률을 서버에 보고. 같은 단계에서 3% 미만 변화는 건너뜀"""
    last = {"pct": -100, "stage": None}

    def f(pct, stage):
        if stage == last["stage"] and pct - last["pct"] < 3 and pct < 100:
            return
        last.update(pct=pct, stage=stage)
        try:
            call(url, body={"a": "progress", "key": key, "nick": p["nick"], "updatedAt": p["updatedAt"], "pct": int(pct), "stage": stage})
        except Exception as e:
            print("진행률 보고 실패", type(e).__name__, file=sys.stderr)
    return f


def run_list(todo, url, key, done):
    for i, p in enumerate(todo):
        reporter(url, key, p)(0, f"대기 중 · 앞에 {i}명" if i else "곧 시작")
    for p in todo:
        t0 = time.time()
        PROG[0] = reporter(url, key, p)
        try:
            res = analyze(p.get("data") or {})
        except Exception as e:
            res = {"updated": TODAY, "basis": "", "trees": [], "notes": [f"계산 오류: {type(e).__name__}"]}
        PROG[0] = None
        w = call(url, body={"a": "result", "key": key, "nick": p["nick"], "updatedAt": p["updatedAt"], "result": res})
        done[p["nick"]] = str(p["updatedAt"])
        # 저장소가 공개라 실행 기록에는 닉네임을 남기지 않는다
        print(f"{len(done)}번째 프로필", len(res["trees"]), "트리", f"{time.time() - t0:.0f}초", w.get("ok"))


if __name__ == "__main__":
    main()
