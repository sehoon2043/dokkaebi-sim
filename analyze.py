# 도사 수첩 자동 분석: 구글 시트(Apps Script)에서 새로 저장된 프로필을 받아 추천 트리를 계산해 돌려준다
#   python analyze.py                 → DOSA_URL·DOSA_KEY 환경변수로 대기 중인 프로필 전부 처리
#   python analyze.py --local p.json  → 로컬 프로필 파일 하나 계산해서 결과 출력(테스트용)
import json, os, sys, time, random, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim"))
import field as F
import mob as M
import transcend as TR
import explain as EX

TODAY = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 9 * 3600))
STYLE_ORDER = ["절명", "연타", "강타", "척살", "저격", "주술", "파멸", "강인", "기동", "헌신", "기만", "제압"]


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
    hl = [h for h in ("생명의 축복", "생명의 흐름")[:heals] if h in owned]
    if len(hl) < heals:
        return None
    aoe = [n for n in M.K if n in owned and n in M.AOE and n not in M.HEALS and M.K[n]["dmg"] > 0]
    yt = [n for n in aoe if M.K[n]["style"] == "연타"]
    pm = [n for n in aoe if M.K[n]["style"] == "파멸"]
    if len(yt) >= 3:
        ult = "폭주"
        core = sorted(yt, key=lambda n: -M.K[n]["dmg"] * min(5, M.TGT.get(n, 1)) / M.K[n]["cd"])[:3]
    elif len(pm) >= 3:
        ult = "대폭발"
        core = sorted(pm, key=lambda n: -M.K[n]["dmg"] * min(5, M.TGT.get(n, 1)) / M.K[n]["cd"])[:3]
    else:
        return None
    fixed = core + (["영혼 소용돌이"] if "영혼 소용돌이" in owned else []) + hl
    free = 8 - len(fixed)
    cand = [n for n in aoe if n not in fixed]
    if len(cand) < free:
        return None
    val = lambda n: M.K[n]["dmg"] * min(5, M.TGT.get(n, 1)) / M.K[n]["cd"]
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
        for i in range(len(fixed), 8):
            for n in cand:
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
    if missing:
        pts.append("안 배운 도술: " + ", ".join(missing) + " (배웠다고 가정하고 계산했습니다)")
    else:
        pts.append("필요한 도술을 모두 배웠습니다.")
    if best:
        k, r = best
        pts.append(f"가장 잘 맞는 용도는 {label[k]}이고, 내 추천 트리보다 약 {abs(r - 1) * 100:.0f}% " + ("좋습니다." if r > 1 else "낮습니다.") if abs(r - 1) >= 0.01 else f"가장 잘 맞는 용도는 {label[k]}이고, 내 추천 트리와 비슷합니다.")
    if ult not in ("폭주", "대폭발"):
        pts.append(f"몰이 점수는 연타·파멸 궁극기 기준 모델이라, 이 덱의 궁극기({ult})·신식 효과와 이동하며 몹을 모으는 효과는 일부만 반영됩니다.")
    pts.append("인기 유저 덱 · 작성 " + (bd.get("author") or {}).get("name", "익명") + f" · 추천 {bd.get('likes', 0)}")
    nm = bd.get("name") or "이름 없는 덱"
    tab = nm if len(nm) <= 14 else nm[:13] + "…"
    t = {"id": f"comm_{bd.get('id')}", "tab": tab, "sub": nm, "slots": names, "ult": ult, "order": order,
         "stat": " · ".join(lines), "points": pts[:2] + [EX.flow(order)] + EX.links(order) + pts[2:], "alt": [], "warn": bool(missing)}
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
        if kind == "boss":
            q = lambda o: F._boss_quick([x for x in o if x != ult])
        else:
            q = lambda o: F.kills([x for x in o if x != ult], o, tr, Ps=F.HUNT_P[:1], syn=(False,))
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
    return [f"배우면 좋은 도술: {EX.josa(n, '을/를')} 배워 {x} 자리에 넣으면 약 +{g * 100:.0f}% (간이 계산)." for g, n, x in top]


# ---------- 결과 조립 ----------
def tree(tid, tab, sub, order, ult, stat, points, alt=None):
    return {"id": tid, "tab": tab, "sub": sub, "slots": arrange(order, ult), "ult": ult, "order": order,
            "stat": stat, "points": EX.points(order, ult, points), "alt": alt or [], "warn": False}


def analyze(data):
    levels = {k: int(v or 0) for k, v in (data.get("levels") or {}).items() if str(v).strip() != ""}
    owned_map = data.get("owned") or {}
    owned = set(owned_map.keys())
    steps = TR.steps_of(owned_map)
    F.set_levels(levels)
    F.set_steps(steps)
    M.setup(levels, steps)
    trees = []
    notes = []
    # 몰이 0/1/2힐
    ref = {"mob": None, "field": None, "boss": None}
    for h, tid, tab in ((0, "mob", "몰이"), (1, "mobheal", "몰이+힐"), (2, "mobheal2", "몰이+2힐")):
        if h == 0:
            r = mob_search(owned, 0)
            prev = r
        else:
            r = mob_add_heal(prev, owned, ("생명의 축복", "생명의 흐름")[h - 1])
            prev = r
        if r and h == 0:
            ref["mob"] = r[0]
        if not r:
            if h == 0:
                notes.append("몰이: 광역 도술이 부족해 계산하지 못했습니다(연타 광역 3개 또는 파멸 광역 3개 필요).")
            continue
        b, o, ult = r
        trees.append(tree(tid, tab, f"힐 {h}개 · 궁극기 {ult}" if h else f"힐 없음 · 궁극기 {ult}", o, ult,
                          "몹 5마리가 뭉쳐 있는 조건" + (" · 공간 결계로 몹이 더 잘 모임(실측 보정)" if M.gathered(o) else ""), [
                              f"하단에 {F.style(ult)} 3개를 두어 궁극기 {EX.josa(ult, '이/가')} 나갑니다.",
                              "영혼 소용돌이가 있으면 맨 앞에서 몹을 모으고 방어력을 깎습니다." if "영혼 소용돌이" in o else "영혼 소용돌이를 배우면 몰이가 더 편해집니다.",
                              "칸은 사용 순서대로 놓았습니다." if not h else f"몰이{'+힐' if h == 2 else ''} 트리에서 한 칸만 {EX.josa(('생명의 축복', '생명의 흐름')[h - 1], '으로/로')} 바꾸고 나머지는 그대로입니다."] + (
                              ["공간 결계는 피해보다 몹을 모으는 효과가 커서 넣었습니다(엽전 비경 실측 기준 약 +6.5%)."] if M.gathered(o) else [])))
    # 필드 사냥: 몹 체력 기준(REF)은 이 사람의 평범(원거리) 트리 초당 피해
    F.REF[0] = 290.0
    rng = F.search(owned, "ranged", False, seeds=4)
    if rng:
        F.REF[0] = F.dps_rate(rng[0][1], rng[0][2])
        rng = F.search(owned, "ranged", False, seeds=4)
    base = rng[0][0] if rng else None
    SEQ = "칸은 사용 순서대로 놓았습니다."

    def rel(v, ref, name):
        if not ref:
            return None
        d = (v / ref - 1) * 100
        return f"{name}보다 약 {abs(d):.0f}% " + ("빠름" if d > 0 else "느림") if abs(d) >= 1 else f"{name}과 비슷"

    def ult_of(o, c):
        return next((x for x in o if F.S.BY[x]["u"]), None) or F.S.ult_for(c)

    def stat(*parts):
        return " · ".join(x for x in parts if x)

    pu = F.search(owned, "pure", False, seeds=4)
    if pu:
        b0, c, o = pu[0]; u = ult_of(o, c)
        trees.append(tree("pure", "완전 단일", f"단일 대상 도술만 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리 (몹 1~5초 처치, 몹 사이 이동 0.3초)", rel(b0, base, "평범 사냥")),
                          ["광역 도술 없이 한 마리만 때리는 트리입니다. 옆 몹을 건드리기 싫거나 몹이 띄엄띄엄 있을 때 쓰세요.", SEQ]))
    puh = F.search(owned, "pure", True, seeds=3)
    if puh:
        b0, c, o = puh[0]; u = ult_of(o, c)
        trees.append(tree("pureh", "완전 단일+힐", f"단일 대상 도술만 + 생명의 축복 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리", rel(b0, pu[0][0] if pu else None, "완전 단일")), ["물약이 많이 들 때 쓰세요.", SEQ]))
    if rng:
        b0, c, o = rng[0]; u = ult_of(o, c)
        trees.append(tree("single", "평범", f"한 마리씩 잡지만 광역 도술 섞음 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리 (몹 1~5초 처치, 몹 사이 이동 0.3초)", rel(b0, pu[0][0] if pu else None, "완전 단일")),
                          ["광역 도술은 몹이 붙어 있으면 덤으로 더 맞습니다. 계산은 몹 한 마리 기준입니다.", f"하단에 {F.style(u)} 3개를 두어 궁극기 {EX.josa(u, '이/가')} 나갑니다.", SEQ],
                          [f"2위({(rng[1][0] / b0 - 1) * 100:+.1f}%): {', '.join(rng[1][1])}"] if len(rng) > 1 else []))
    rh = F.search(owned, "ranged", True, seeds=4)
    if rh:
        b0, c, o = rh[0]; u = ult_of(o, c)
        trees.append(tree("singleh", "평범+힐", f"평범 사냥 + 생명의 축복 · 궁극기 {u}", o, u,
                          stat(f"1분에 약 {b0:.1f}마리", rel(b0, base, "평범 사냥")), ["물약이 많이 들면 이 트리를 쓰세요. 원거리라 근접 절명보다 덜 맞습니다.", SEQ]))
    for heal, tid, tab in ((False, "jhunt", "절명"), (True, "jhunt_h", "절명+힐")):
        me = F.search(owned, "melee", heal, seeds=4 if not heal else 3)
        if not me:
            continue
        b0, c, o = me[0]
        k04 = F.kills(c, o, 0.4)
        k10 = F.kills(c, o, 1.0)
        trees.append(tree(tid, tab, "근접 필드 사냥" + (", 힐 1개" if heal else ", 힐 없음") + " · 궁극기 암습", o, "암습",
                          stat(f"1분에 약 {b0:.1f}마리 (몹 사이 이동 0.7초)", f"촘촘하면(0.4초) 약 {k04:.1f}마리", f"흩어져 있으면(1초) 약 {k10:.1f}마리"),
                          ["몹이 촘촘히 붙어 있는 곳에서 가장 빠르고, 흩어져 있으면 평범(원거리)과 같거나 느립니다." if not heal else "힐을 넣을 거면 보통 평범+힐(원거리)이 더 빠르고 덜 맞습니다.",
                           "하단에 절명 3개를 두어 암습이 나갑니다. 암습은 순서 뒤쪽이라 다른 도술이 쿨일 때만 씁니다.", SEQ]))
    ref["field"] = base
    bs = F.boss_search(owned, seeds=5)
    if bs:
        ref["boss"] = bs[0][0]
    if bs:
        b, c, o = bs[0]
        trees.append(tree("boss", "절명 보스", "절명 + 저격, 기습 안 씀 · 궁극기 암습", o, "암습", "보스·필드보스·레이드용",
                          ["보스·필드보스·레이드용입니다. 하단에 절명 3개를 두어 암습이 나갑니다.", "칸은 사용 순서대로 놓았습니다."],
                          [f"2위({(bs[1][0] / b - 1) * 100:+.1f}%): {', '.join(bs[1][1])}"] if len(bs) > 1 else []))
    # 주력 스타일별 트리: 공격 도술 3개 이상 배운 스타일마다 보스(궁극기 그 스타일) · 사냥
    P = F.pool(owned)
    cnt = {st: sum(F.style(n) == st for n in P if n not in F.HEALS) for st in STYLE_ORDER}
    for st in sorted([x for x in STYLE_ORDER if cnt[x] >= 3], key=lambda x: -cnt[x]):
        if st != "절명":
            bs2 = F.boss_search(owned, seeds=3, st=st)
            if bs2:
                b, c, o = bs2[0]
                u = F.S.ULT_OF.get(st)
                cmp_ = ""
                if bs:
                    d = (b / bs[0][0] - 1) * 100
                    cmp_ = " · 절명 보스와 비슷" if abs(d) < 1 else f" · 절명 보스보다 약 {abs(d):.0f}% " + ("높음" if d > 0 else "낮음")
                ref["boss"] = max(ref["boss"] or 0, b)
                trees.append(tree("boss_" + st, st + " 보스", f"{st} 위주 · 궁극기 {u}", o, u, "보스·필드보스·레이드용" + cmp_,
                                  [f"하단에 {st} 3개를 두어 궁극기 {EX.josa(u, '이/가')} 나갑니다.", SEQ]))
        if st not in ("절명", "저격", "파멸"):
            hs = F.style_hunt(owned, st, seeds=3)
            if hs:
                b, c, o, tr_ = hs[0]
                u = F.S.ULT_OF.get(st)
                trees.append(tree("hunt_" + st, st + " 사냥", f"{st} 위주 필드 사냥 · 궁극기 {u}", o, u,
                                  stat(f"1분에 약 {b:.1f}마리 (몹 사이 이동 {tr_}초)", rel(b, base, "평범 사냥")),
                                  [f"하단에 {st} 3개를 두어 궁극기 {EX.josa(u, '이/가')} 나갑니다.", SEQ]))
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
            t["points"] = t["points"][:-1] + sg + t["points"][-1:] if t["points"] and t["points"][-1].startswith("신식") else t["points"] + sg
    # 커뮤니티 덱(깨비지지 유저 덱, 인기순) — 이 사람 강화·돌파 기준 점수와 내 추천 대비
    for bd in BUILDS:
        try:
            trees.append(community(bd, owned, ref))
        except Exception as e:
            notes.append(f"커뮤니티 덱 '{bd.get('name', '')[:20]}' 계산 실패({type(e).__name__})")
    lv = " · ".join(f"{s} {levels[s]}" for s in STYLE_ORDER if levels.get(s))
    br = f" · 돌파 반영 {len(steps)}개" if steps else ""
    return {"updated": TODAY, "basis": (lv or "강화 정보 없음") + br + ", 도술 8칸", "trees": trees, "notes": notes}


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
    BUILDS[:] = load_builds()
    print("커뮤니티 덱", len(BUILDS))
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


def run_list(todo, url, key, done):
    for p in todo:
        t0 = time.time()
        try:
            res = analyze(p.get("data") or {})
        except Exception as e:
            res = {"updated": TODAY, "basis": "", "trees": [], "notes": [f"계산 오류: {type(e).__name__}"]}
        w = call(url, body={"a": "result", "key": key, "nick": p["nick"], "updatedAt": p["updatedAt"], "result": res})
        done[p["nick"]] = str(p["updatedAt"])
        print(p["nick"], len(res["trees"]), "트리", f"{time.time() - t0:.0f}초", w.get("ok"))


if __name__ == "__main__":
    main()
