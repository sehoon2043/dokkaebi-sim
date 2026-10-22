# 커뮤니티 덱(깨비지지 덱 게시판) 분류: 사냥터(제목·본문 키워드) · 광역/단일(범위 도술 수) · 생존/믹스/딜(유지 도술 수)
#   순서: 10/21 패치 이후 글만 → 내가 가진 도술로 바로 쓸 수 있는 것 먼저 → 추천 수 많은 순(비추천 1개 = 추천 2개 감점)
import json, os, re
import sustain as SU
import timeline as S

TGT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "targets.json"), encoding="utf-8"))
# 사냥터 키 → 이름(칩 순서). 비경 3종은 이름을 받기 전까지 하나
GROUNDS = {"wild": "황무지", "well": "우물동굴 215k", "mine": "음산한 폐광 260k", "k290": "290k", "k310": "310k~335k",
           "k360": "360k~385k", "k400": "400k 이상", "secret": "비경", "boss": "보스"}
KEYWORDS = {"wild": ["황무지"], "well": ["우물", "215k"], "mine": ["폐광", "260k"], "secret": ["비경"], "boss": ["보스", "레이드", "필보"]}
# 260k 위 사냥터: 커뮤니티가 이름보다 전투력 숫자(290k·335k 등)로 불러서 글에 적힌 'NNNk' 숫자 범위로 나눈다
HIGH = [("k290", 280, 300), ("k310", 300, 350), ("k360", 350, 400), ("k400", 400, 1000)]
KNUM = re.compile(r"(?<!\d)(\d{3}) ?k(?![a-z])")
PATCH_AT = 1792508400   # 2026-10-21 00:00 KST
AOE_MIN = 4             # 8칸 중 범위 도술(대상 2명 이상)이 이만큼이면 광역
PER_CARD = 10
UNASSIGNED = 30
VIDEO = re.compile(r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be|chzzk\.naver\.com|(?:[\w-]+\.)?sooplive\.co\.kr|(?:[\w-]+\.)?afreecatv\.com)\S*")


def _num(v):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def at_of(bd):
    """작성 시각(초). 이상한 값이면 0(패치 전으로 봄)"""
    return _num(bd.get("created_at"))


def parse(bd):
    """덱 → {id, name, author, likes, dislikes, at, body, slots, order, ult}. 궁극기 없음·빈 칸·모르는 도술·형식 오류면 None"""
    try:
        slots = [x.get("name") for x in bd.get("slots") or []]
        ult = (bd.get("ult") or {}).get("name")
        if not slots or not isinstance(ult, str) or not all(isinstance(n, str) for n in slots) or any(n not in S.BY for n in slots + [ult]):
            return None
        order = [x["name"] for x in (bd.get("order") or bd["slots"]) if isinstance(x, dict) and x.get("name") in slots]
        order += [n for n in slots if n not in order]   # 순서 목록이 모자라면 칸 순서로 채움
        order.insert(max(0, min(len(order), _num(bd.get("ult_at")))), ult)
        if bd.get("id") is None:
            return None
        return {"id": bd["id"], "name": str(bd.get("name") or "이름 없는 덱"), "author": str((bd.get("author") or {}).get("name") or "익명"),
                "likes": _num(bd.get("likes")), "dislikes": _num(bd.get("dislikes")), "at": at_of(bd),
                "body": str(bd.get("body") or ""), "slots": slots, "order": order, "ult": ult}
    except (AttributeError, TypeError, KeyError):
        return None


def grounds_of(d):
    txt = (d["name"] + " " + d["body"]).lower()
    gs = {g for g, ks in KEYWORDS.items() if any(k in txt for k in ks)}
    nums = [int(n) for n in KNUM.findall(txt)]
    gs |= {g for g, lo, hi in HIGH if any(lo <= n < hi for n in nums)}
    return [g for g in GROUNDS if g in gs]


def style_of(d):
    return "광역" if sum(TGT.get(n, 1) >= 2 for n in d["slots"]) >= AOE_MIN else "단일"


def tier_of(d):
    n = SU.count(d["order"])
    return "딜" if n == 0 else "믹스" if n == 1 else "생존"


def video(d):
    m = VIDEO.search(d.get("body") or "")
    return m.group(0) if m else None


def missing(d, owned):
    return [n for n in d["slots"] if n not in owned]


def rank(ds, owned):
    return sorted(ds, key=lambda d: (bool(missing(d, owned)), -(d["likes"] - 2 * d["dislikes"]), d["id"]))


def classify(raw, owned):
    """(placed, unassigned, info): placed[사냥터][광역|단일|보스][딜|믹스|생존] = [덱 id](최대 PER_CARD),
    unassigned = 사냥터가 안 적힌 덱 id(최대 UNASSIGNED), info[id] = 화면에 보여 줄 덱 정보"""
    ds, seen = [], set()
    for d in (parse(b) for b in raw):
        if d and d["at"] >= PATCH_AT and d["id"] not in seen:   # 인기순 페이지가 받는 도중 밀리면 같은 덱이 두 번 올 수 있음
            seen.add(d["id"])
            ds.append(d)
    placed, un = {}, []
    for d in rank(ds, owned):
        gs = grounds_of(d)
        if not gs:
            un.append(d["id"])
        for g in gs:
            st = "보스" if g == "boss" else style_of(d)
            placed.setdefault(g, {}).setdefault(st, {}).setdefault(tier_of(d), []).append(d["id"])
    for g in placed.values():
        for st in g.values():
            for t in st:
                st[t] = st[t][:PER_CARD]
    un = un[:UNASSIGNED]
    keep = {i for g in placed.values() for st in g.values() for v in st.values() for i in v} | set(un)
    info = {d["id"]: {"name": d["name"], "author": d["author"], "likes": d["likes"], "video": video(d), "slots": d["slots"],
                      "order": d["order"], "ult": d["ult"], "missing": missing(d, owned)} for d in ds if d["id"] in keep}
    return placed, un, info
