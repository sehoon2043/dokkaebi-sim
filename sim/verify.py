# 추천 트리 검증
#   탐색 검증: 추천 트리에서 한 칸만 다른 도술로 바꾼 조합을 전부 같은 계산으로 비교한다
#   가정 흔들기: 확실하지 않은 가정값(방어력 감소 효과, 지속 피해, 몹 체력 등)을 바꿔 가며 위 비교를 다시 한다
# 바꾼 조합이 추천보다 FLIP 이상 좋으면 '조건에 따라 바뀜'으로 기록한다
import copy
import field as F
import mob as M

S = F.S
FLIP = 0.02     # 가정을 바꿨을 때 이만큼 넘게 좋아지는 조합이 있으면 1위가 바뀐 것으로 본다
MISS = 0.005    # 원래 가정에서 이만큼 넘게 좋아지는 조합이 있으면 탐색이 놓친 것
HEALS = F.HEALS


# ---------- 가정 바꾸기 ----------
def _set(mod, name, val):
    old = getattr(mod, name)
    setattr(mod, name, val)
    return lambda: setattr(mod, name, old)


def _p_scale(i, f):
    """HUNT_P·BOSS_P (저격 보정, 암습 보정, 검의 형상 쿨 감소) 중 i번째 값에 f를 곱한다"""
    def ap():
        r1 = _set(F, "HUNT_P", [tuple(x * f if j == i else x for j, x in enumerate(p)) for p in F.HUNT_P])
        r2 = _set(F, "BOSS_P", [tuple(x * f if j == i else x for j, x in enumerate(p)) for p in F.BOSS_P])
        return lambda: (r1(), r2())
    return ap


def _dot(f):
    def ap():
        r1 = _set(S, "DOT", {k: v * f for k, v in S.DOT.items()})
        r2 = _set(M, "DOTV", {k: v * f for k, v in M.DOTV.items()})
        return lambda: (r1(), r2())
    return ap


def _arm(v):
    def ap():
        r1 = _set(S, "ARM", v)
        r2 = _set(M, "ARMOR", v)
        return lambda: (r1(), r2())
    return ap


def _amp(f):
    return lambda: _set(F, "AMP0", {k: v * f for k, v in F.AMP0.items()})


CTX = {"syn": (True, False), "tr": 1.0}


def _ctx(**kw):
    def ap():
        old = dict(CTX)
        CTX.update(kw)
        return lambda: (CTX.clear(), CTX.update(old))
    return ap


def _nosyn():
    r1 = _set(S, "SYN", False)
    r2 = _ctx(syn=(False,))()
    return lambda: (r1(), r2())


def _mob3():
    old = M.w
    M.w = lambda o: (M.GATHER_BONUS if M.gathered(o) else 1.0) * M.sc(o, 3)
    return lambda: setattr(M, "w", old)


# (이름, 적용 대상, 적용 함수)  대상: mob 몰이 / field 필드 사냥 / boss 보스
SCENS = [
    ("방어력 감소 효과가 2배일 때", "mob field boss", _arm(0.10)),
    ("방어력 감소 효과가 없을 때", "mob field boss", _arm(0.0)),
    # 필드 처치 계산은 지속 피해를 넣지 않아서(몹이 금방 죽음) 지속 피해 가정은 몰이·보스에만
    ("지속 피해가 절반일 때", "mob boss", _dot(0.5)),
    ("지속 피해가 1.5배일 때", "mob boss", _dot(1.5)),
    ("상태 이상 연계가 없을 때", "field boss", _nosyn),
    ("도술 사이 딜레이가 2배일 때", "field", lambda: _set(F, "OH", F.OH * 2)),
    ("도술 사이 딜레이가 절반일 때", "field", lambda: _set(F, "OH", F.OH / 2)),
    ("도술 사이 딜레이가 0.15초일 때", "boss", lambda: _set(F, "OH_BOSS", 0.15)),
    ("평타 동작이 0.9초일 때", "boss", lambda: _set(F, "BASIC_I", 0.9)),
    ("평타 동작이 0.6초일 때", "boss", lambda: _set(F, "BASIC_I", 0.6)),
    ("저격 피해가 10% 더 셀 때", "field boss", _p_scale(0, 1.10)),
    ("저격 피해가 10% 약할 때", "field boss", _p_scale(0, 0.90)),
    ("검의 형상 쿨 감소가 절반일 때", "field boss", _p_scale(2, 0.5)),
    ("받는 피해 증가(요혼격 등)가 절반일 때", "boss", _amp(0.5)),
    ("평타 피해가 절반일 때", "boss", lambda: _set(F, "BASIC_BOSS", F.BASIC_BOSS * 0.5)),
    ("평타 피해가 1.5배일 때", "boss", lambda: _set(F, "BASIC_BOSS", F.BASIC_BOSS * 1.5)),
    ("몹 체력이 0.6배일 때(약한 사냥터)", "field", lambda: _set(F, "HS", tuple(x * 0.6 for x in F.HS))),
    ("몹 체력이 1.6배일 때(강한 사냥터)", "field", lambda: _set(F, "HS", tuple(x * 1.6 for x in F.HS))),
    ("몹 사이 이동이 2배일 때", "field", _ctx(tr=2.0)),
    ("공간 결계 모으기 효과가 없을 때", "mob", lambda: _set(M, "GATHER_BONUS", 1.0)),
    ("공간 결계 모으기 효과가 2배일 때", "mob", lambda: _set(M, "GATHER_BONUS", 1 + (M.GATHER_BONUS - 1) * 2)),
    ("몹이 3마리만 모일 때", "mob", _mob3),
]


# ---------- 트리 종류별 계산 ----------
def spec(tid, owned):
    """트리 id로 후보 도술·계산 방식을 정한다. 검증 대상이 아니면 None"""
    P = F.pool(owned)
    if tid.startswith("mob"):
        pool = [n for n in M.K if n in owned and n in M.AOE and n not in M.HEALS and M.K[n]["dmg"] > 0]
        # 영혼 소용돌이는 모으기·방어력 감소 때문에 몰이에 고정(계산에 모으기 효과가 다 안 들어감)
        return {"kind": "mob", "pool": pool, "fixed": {"영혼 소용돌이"}}
    if tid == "boss" or tid.startswith("boss_"):
        return {"kind": "boss", "pool": [n for n in P if n != "기습" and n not in HEALS], "fixed": set()}
    if tid in ("pure", "pureh"):
        pool = [n for n in P if F.style(n) in ("저격", "파멸") and F.TGT.get(n, 1) == 1]
        tr = 0.3
    elif tid in ("single", "singleh"):
        pool = [n for n in P if F.style(n) in ("저격", "파멸")]
        tr = 0.3
    elif tid.startswith("jhunt"):
        pool = [n for n in P if n != "기습" and n not in HEALS]
        tr = 0.7
    elif tid.startswith("hunt_"):
        st = tid[5:]
        pool = [n for n in P if n != "기습" and n not in HEALS]
        kind = {"절명": "근", "연타": "근", "강타": "근", "척살": "근", "저격": "원", "주술": "원", "파멸": "원"}.get(st)
        tr = 0.7 if kind == "근" else (0.3 if kind == "원" else 0.5)
    else:
        return None
    return {"kind": "field", "pool": pool, "tr": tr, "fixed": set()}


def _ok(o, u):
    us = F.style(u)
    return sum(F.style(x) == us for x in o if x != u and x not in HEALS) >= 3


def score(sp, o, u, arrange):
    if sp["kind"] == "mob":
        return M.w(o)
    names = arrange(o, u)
    if sp["kind"] == "boss":
        return F.boss_score(names, o)
    return F.kills(names, o, sp["tr"] * CTX["tr"], Ps=F.HUNT_P, syn=CTX["syn"])


def neighbors(sp, o, u):
    """한 칸만 다른 도술로 바꾼 순서들: (빠진 도술, 들어간 도술, 순서)"""
    out = []
    for i, x in enumerate(o):
        if x == u or x in HEALS or x in sp["fixed"]:
            continue
        for n in sp["pool"]:
            if n in o:
                continue
            t = o[:]
            t[i] = n
            if not _ok(t, u):
                continue
            if sp["kind"] == "mob" and not M.valid_order(t):
                continue
            out.append((x, n, t))
    return out


def heal_neighbors(parent, u, heal):
    """몰이+힐: 부모 트리에서 힐로 바꿀 칸만 다르게 고른 순서들"""
    out = []
    for i, x in enumerate(parent):
        if x == u or x in M.HEALS or x == "영혼 소용돌이":
            continue
        t = parent[:]
        t[i] = heal
        if _ok(t, u) and M.valid_order(t):
            out.append((x, heal, t))
    return out


def _best(sp, o, u, nb, arrange):
    base = score(sp, o, u, arrange)
    best = None
    for x, n, t in nb:
        if t == o:
            continue
        v = score(sp, t, u, arrange)
        if not best or v > best[0]:
            best = (v, x, n, t)
    if not best or base <= 0:
        return base, None
    return base, (best[0] / base - 1, best[1], best[2], best[3])


def polish(tid, owned, o, u, arrange, reopt, rounds=3):
    """탐색 보강: 한 칸 바꾼 조합 중 더 좋은 게 있으면 바꾸고 순서를 다시 맞춘다. (점수, 순서, 바꾼 기록)"""
    sp = spec(tid, owned)
    if not sp or not _ok(o, u):
        return None
    log = []
    b = score(sp, o, u, arrange)
    for _ in range(rounds):
        nb = neighbors(sp, o, u)
        _, best = _best(sp, o, u, nb, arrange)
        if not best or best[0] <= 1e-4:
            break
        b2, o2 = reopt(best[3])
        if b2 <= b:
            break
        log.append((best[1], best[2]))
        b, o = b2, o2
    return b, o, log


def check(t, owned, arrange, parent=None):
    """트리 하나 검증. 결과 dict 또는 None(대상 아님)"""
    sp = spec(t["id"], owned)
    if not sp or not t.get("order") or not t.get("ult"):
        return None
    o, u = t["order"], t["ult"]
    if not _ok(o, u):
        return None
    if parent:
        heal = [x for x in o if x in M.HEALS and x not in parent][0]
        nb = heal_neighbors(parent, u, heal)
        what = f"힐 넣을 칸 후보 {len(nb)}곳"
    else:
        nb = neighbors(sp, o, u)
        what = f"한 칸만 바꾼 조합 {len(nb)}개"
    if not nb:
        return None
    _, b0 = _best(sp, o, u, nb, arrange)
    flips = []
    sc = [s for s in SCENS if sp["kind"] in s[1].split()]
    for name, _, ap in sc:
        undo = ap()
        try:
            _, b = _best(sp, o, u, nb, arrange)
        finally:
            undo()
        if b and b[0] > FLIP:
            flips.append({"when": name, "out": b[1], "in": b[2], "gain": round(b[0] * 100, 1)})
    miss = None
    if b0 and b0[0] > MISS:
        miss = {"out": b0[1], "in": b0[2], "gain": round(b0[0] * 100, 1)}
    v = {"what": what, "nb": len(nb), "n": len(sc), "ok": len(sc) - len(flips), "flips": flips, "miss": miss, "heal": bool(parent)}
    v["lines"] = lines(v)
    return v


def lines(v):
    """검증 결과 설명 줄"""
    from explain import josa
    out = []
    if v["miss"]:
        m = v["miss"]
        out.append(f"{josa(m['out'], '을/를')} {josa(m['in'], '으로/로')} 바꾸면 약 {m['gain']:.1f}% 좋아져서, 이 트리가 최선이 아닐 수 있습니다.")
    else:
        out.append(f"{v['what']}보다 좋거나 같습니다.")
    if not v["flips"]:
        out.append(f"확실하지 않은 가정 {v['n']}가지를 하나씩 바꿔 다시 계산해도 이 트리가 1위입니다.")
        return out
    out.append(f"확실하지 않은 가정 {v['n']}가지를 하나씩 바꿔 다시 계산하면 {v['ok']}가지에서 1위를 지킵니다.")
    grp = {}
    for f in v["flips"]:
        g = grp.setdefault((f["out"], f["in"]), [])
        g.append(f)
    for (a, b), fs in sorted(grp.items(), key=lambda kv: -max(f["gain"] for f in kv[1]))[:3]:
        whens = " · ".join(f["when"] for f in fs[:3]) + (f" 외 {len(fs) - 3}가지" if len(fs) > 3 else "")
        g = max(f["gain"] for f in fs)
        if v["heal"]:
            out.append(f"{whens}: 힐을 {a} 자리에 넣는 쪽이 최대 {g:.0f}% 낫습니다.")
        else:
            out.append(f"{whens}: {josa(a, '을/를')} {josa(b, '으로/로')} 바꾸면 최대 {g:.0f}% 낫습니다.")
    return out
