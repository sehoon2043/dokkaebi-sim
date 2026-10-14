# 도사 수첩 자동 분석: 구글 시트(Apps Script)에서 새로 저장된 프로필을 받아 추천 트리를 계산해 돌려준다
#   python analyze.py                 → DOSA_URL·DOSA_KEY 환경변수로 대기 중인 프로필 전부 처리
#   python analyze.py --local p.json  → 로컬 프로필 파일 하나 계산해서 결과 출력(테스트용)
import json, os, sys, time, random, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "sim"))
import field as F
import mob as M

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


# ---------- 결과 조립 ----------
def tree(tid, tab, sub, order, ult, stat, points, alt=None):
    return {"id": tid, "tab": tab, "sub": sub, "slots": arrange(order, ult), "ult": ult, "order": order,
            "stat": stat, "points": points, "alt": alt or [], "warn": False}


def analyze(data):
    levels = {k: int(v or 0) for k, v in (data.get("levels") or {}).items() if str(v).strip() != ""}
    owned = set((data.get("owned") or {}).keys())
    F.set_levels(levels)
    M.setup(levels)
    trees = []
    notes = []
    # 몰이 0/1/2힐
    for h, tid, tab in ((0, "mob", "몰이"), (1, "mobheal", "몰이+힐"), (2, "mobheal2", "몰이+2힐")):
        r = mob_search(owned, h)
        if not r:
            if h == 0:
                notes.append("몰이: 광역 도술이 부족해 계산하지 못했습니다(연타 광역 3개 또는 파멸 광역 3개 필요).")
            continue
        b, o, ult = r
        trees.append(tree(tid, tab, f"힐 {h}개 · 궁극기 {ult}" if h else f"힐 없음 · 궁극기 {ult}", o, ult,
                          f"몹 5마리 뭉친 조건 몰이 점수 {b:.0f}", [
                              f"하단에 {F.style(ult)} 3개를 두어 궁극기 {ult}가 나갑니다.",
                              "영혼 소용돌이가 있으면 맨 앞에서 몹을 모으고 방어력을 깎습니다." if "영혼 소용돌이" in o else "영혼 소용돌이를 배우면 몰이가 더 편해집니다.",
                              "칸은 사용 순서대로 놓았습니다."]))
    # 필드 사냥: 몹 체력 기준(REF)은 이 사람의 원거리 단일 트리 초당 피해
    F.REF[0] = 290.0
    rng = F.search(owned, "ranged", False, seeds=4)
    if rng:
        F.REF[0] = F.dps_rate(rng[0][1], rng[0][2])
        rng = F.search(owned, "ranged", False, seeds=4)
    base = rng[0][0] if rng else None
    if rng:
        b, c, o = rng[0]
        ult = next((x for x in o if F.S.BY[x]["u"]), None) or F.S.ult_for(c)
        trees.append(tree("single", "단일", f"원거리 필드 사냥 · 궁극기 {ult}", o, ult, f"처치 속도 {b:.1f}마리/분 (몹 1~5초 처치, 이동 0.3초)",
                          ["몹 한 마리씩 잡는 필드 기준이고, 광역 도술은 몹이 붙어 있으면 덤으로 더 맞습니다.", "칸은 사용 순서대로 놓았습니다."],
                          [f"2위({(rng[1][0] / b - 1) * 100:+.1f}%): {', '.join(rng[1][1])}"] if len(rng) > 1 else []))
    rh = F.search(owned, "ranged", True, seeds=4)
    if rh:
        b, c, o = rh[0]
        ult = F.S.ult_for(c)
        trees.append(tree("singleh", "단일+힐", f"원거리 필드 사냥 힐 1개 · 궁극기 {ult}", o, ult,
                          f"처치 속도 {b:.1f}마리/분" + (f" (힐 없는 단일 대비 {(b / base - 1) * 100:+.1f}%)" if base else ""),
                          ["물약이 많이 들면 이 트리를 쓰세요.", "칸은 사용 순서대로 놓았습니다."]))
    me = F.search(owned, "melee", False, seeds=4)
    if me:
        b, c, o = me[0]
        k04 = F.kills(c, o, 0.4)
        k10 = F.kills(c, o, 1.0)
        rel = (lambda v: f"{(v / base - 1) * 100:+.0f}%") if base else (lambda v: f"{v:.1f}마리/분")
        trees.append(tree("jhunt", "절명 사냥", "근접 필드 사냥 · 궁극기 암습", o, "암습",
                          f"처치 속도 {b:.1f}마리/분 (몹 사이 이동 0.7초)" + (f" · 원거리 단일 대비 {rel(b)}" if base else ""),
                          ["하단에 절명 3개를 두어 암습이 나갑니다. 암습은 순서 뒤쪽이라 다른 도술이 쿨일 때만 씁니다.",
                           f"몹이 촘촘하면(이동 0.4초) {rel(k04)}, 흩어져 있으면(1초) {rel(k10)}입니다.",
                           "칸은 사용 순서대로 놓았습니다."]))
    bs = F.boss_search(owned, seeds=5)
    if bs:
        b, c, o = bs[0]
        trees.append(tree("boss", "보스", "절명 + 저격 보스, 기습 안 씀 · 궁극기 암습", o, "암습", f"보스 DPS 점수 {b:.0f}",
                          ["보스·필드보스·레이드용입니다. 하단에 절명 3개를 두어 암습이 나갑니다.", "칸은 사용 순서대로 놓았습니다."],
                          [f"2위({(bs[1][0] / b - 1) * 100:+.1f}%): {', '.join(bs[1][1])}"] if len(bs) > 1 else []))
    lv = " · ".join(f"{s} {levels[s]}" for s in STYLE_ORDER if levels.get(s))
    return {"updated": TODAY, "basis": (lv or "강화 정보 없음") + ", 도술 8칸", "trees": trees, "notes": notes}


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
        t0 = time.time()
        res = analyze(d.get("data", d))
        print(json.dumps(res, ensure_ascii=False, indent=1))
        print(f"# {time.time() - t0:.0f}초", file=sys.stderr)
        return
    url = os.environ["DOSA_URL"]
    key = os.environ["DOSA_KEY"]
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
