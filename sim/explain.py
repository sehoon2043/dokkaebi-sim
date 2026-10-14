# 추천 트리 자동 설명: 사용 순서 흐름, 도술 연계, 신식 활용
import json, os

_D = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "skills.json"), encoding="utf-8"))
STYLE_AW = {s["n"]: s.get("aw", "") for s in _D["styles"]}
STYLE_OF = {k["n"]: _D["styles"][k["st"]]["n"] for k in _D["skills"]}
ULT_STYLE = {k["n"]: _D["styles"][k["st"]]["n"] for k in _D["skills"] if k["u"]}
TGT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "targets.json"), encoding="utf-8"))

# 도술이 거는 효과(짧은 이름)
GIVE = {
    "영혼 소용돌이": ["모으기", "방어력 감소", "저주"], "연쇄 타격": ["방어력 감소"],
    "요혼격": ["받는 피해 +10%"], "꿰뚫는 저격": ["받는 피해 +10%"], "공간 결계": ["모으기", "받는 피해 +5%"],
    "화염구": ["화상"], "폭발하는 화살": ["화상"], "하늘의 심판": ["화상"],
    "번개 폭풍": ["감전"], "일섬": ["감전"],
    "부적 던지기": ["저주"], "살 날리기": ["저주"], "신벌의 영역": ["저주"], "저주 내리기": ["저주"],
    "환영 참격": ["출혈"], "급소 관통": ["출혈"],
    "얼음화살": ["동상"], "날카로운 얼음창": ["동상"],
    "내려찍기": ["낙인"], "약점 베기": ["낙인"],
    "주먹 지르기": ["충격"], "연속 충격": ["충격"],
    "휘둘러 내려치기": ["파쇄"], "회전 난격": ["파쇄"], "휘둘러치기": ["파쇄"],
    "크게 베기": ["파열"], "검기 날리기": ["파열"], "삼단 찌르기": ["관통"],
    "낙뢰": ["원소"], "화염 분출": ["원소"], "붕괴하는 대지": ["원소"], "연쇄 번개": ["원소"],
    "생명의 축복": ["회복"], "생명의 흐름": ["지속 회복"],
}
# (받는 쪽 도술, 필요한 효과, 이득)
NEED = [
    ("얼음화살", "원소", "피해 +34.8%"), ("쇠뇌 사격", "동상", "피해 +18%"), ("사격", "파쇄", "피해 +14%"),
    ("약점 베기", "원소", "피해 +26.5%"), ("심장 절단", "출혈", "피해 +10.7%"), ("삼단 찌르기", "충격", "피해 +12.7%"),
    ("폭주", "화상", "타격마다 추가 피해"),
    ("내려찍기", "파열", "받는 피해 +5%"), ("내려치기", "파열", "받는 피해 +5%"),
    ("화염 분출", "파쇄", "받는 피해 +5%"), ("연쇄 번개", "파쇄", "받는 피해 +5%"),
    ("낙뢰", "관통", "방어력 감소 5%"), ("올려치기", "관통", "방어력 감소 5%"),
]
SHORT = {"영혼 소용돌이": "소용돌이", "날카로운 얼음창": "얼음창"}


def _s(n):
    return SHORT.get(n, n)


def josa(word, pair):
    """받침에 맞는 조사: pair = '이/가', '은/는', '을/를', '으로/로'"""
    a, b = pair.split("/")
    ch = word[-1] if word else ""
    if not ("가" <= ch <= "힣"):
        return word + b
    jong = (ord(ch) - 0xAC00) % 28
    if pair == "으로/로":
        return word + (b if jong in (0, 8) else a)
    return word + (a if jong else b)


def flow(order):
    """사용 순서를 역할과 함께 한 줄로"""
    parts = []
    for n in order:
        g = GIVE.get(n, [])
        if n in ULT_STYLE:
            parts.append(f"{_s(n)}(궁극기)")
        elif g:
            parts.append(f"{_s(n)}({'·'.join(g)})")
        else:
            parts.append(_s(n) + ("(광역)" if TGT.get(n, 1) > 1 else ""))
    return "흐름: " + " → ".join(parts) + "."


def links(order):
    """트리 안에서 실제로 이어지는 연계와 놓친 연계"""
    have = {}
    for n in order:
        for g in GIVE.get(n, []):
            have.setdefault(g, []).append(n)
    got, miss = [], []
    for tgt, need, gain in NEED:
        if tgt not in order:
            continue
        src = [x for x in have.get(need, []) if x != tgt]
        if src:
            got.append(f"{'·'.join(_s(x) for x in src)}의 {need} → {_s(tgt)} {gain}")
        elif need in ("원소", "동상", "화상"):
            miss.append(f"{josa(_s(tgt), '은/는')} {josa(need, '이/가')} 있을 때 {gain}인데 이 트리엔 {josa(need, '을/를')} 거는 도술이 없습니다")
    out = []
    if got:
        out.append("연계: " + " / ".join(got) + ".")
    if miss:
        out.append("놓친 연계: " + " / ".join(miss[:2]) + ".")
    amp = [x for x in order if x in ("요혼격", "꿰뚫는 저격", "공간 결계")]
    if amp:
        out.append(f"{josa('·'.join(_s(x) for x in amp), '으로/로')} 받는 피해를 올린 뒤 5초 안에 큰 도술이 들어가도록 순서를 맞췄습니다(몹이 금방 죽는 필드에서는 효과가 작습니다).")
    return out


def style_note(ult):
    st = ULT_STYLE.get(ult)
    if not st:
        return []
    aw = STYLE_AW.get(st, "")
    tips = {
        "연타": "연타 도술을 쉬지 않고 맞혀 격노를 유지하는 게 핵심입니다. 지속 피해(화상·저주)도 격노 유지에 도움이 됩니다.",
        "파멸": "파멸 도술을 쓸수록 영력이 차고, 가득 차면 요기범람으로 도술 쿨이 초기화되고 시전이 빨라집니다. 파멸 도술을 자주 쓰게 둘수록 좋습니다.",
        "절명": "모든 도술이 검의 형상을 1개씩 채웁니다. 동작이 짧고 쿨이 짧은 도술이 많을수록 암습 쿨이 자주 줄어듭니다.",
        "저격": "일정 시간마다 화살촉이 쌓이고, 화살촉이 있으면 저격 외 도술 피해가 오르고 저격 도술이 화살촉을 소모해 강해집니다.",
        "기동": "도술·귀보로 영력을 채우면 궁극기 쿨이 초기화되고 연쇄가 켜집니다. 쿨 짧은 기동 도술을 자주 쓰는 구성이 유리합니다.",
    }
    t = tips.get(st)
    return [f"신식({st}): " + (t if t else aw)] if (t or aw) else []


def points(order, ult, extra_first=()):
    o = [x for x in order]
    out = list(extra_first)
    out.append(flow(o))
    out += links(o)
    out += style_note(ult)
    return out
