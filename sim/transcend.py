# 도술 돌파(1~10단계) 효과 — 10/14 패치 규칙 적용
# data/transcend.json: 패치 전 10단계 총 성장량(쿨타임 감소 cd10초, 피해 +dmg10%)
# 패치 규칙: 총 성장량은 유지하고 단계마다 같은 폭으로 성장. 쿨타임 감소는 10단계 기준 기본 쿨의 15%까지,
# 넘치는 쿨 감소는 피해량 증가로 바뀜(같은 초당 피해가 되게 환산). 쿨 감소만 있는 도술은 15% 제한 없음.
import json, os

T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "transcend.json"), encoding="utf-8"))
CAP = 0.15


def effect(name, step, base_cd):
    """(새 쿨타임, 피해 배율). 돌파 정보가 없거나 0단계면 (base_cd, 1.0)"""
    t = T.get(name)
    step = max(0, min(int(step or 0), (t or {}).get("mx", 10)))
    if not t or step == 0 or not base_cd:
        return base_cd, 1.0
    f = step / 10.0
    cd10 = t["cd10"]
    dmg10 = t["dmg10"] / 100.0
    if dmg10 > 0 and cd10 > CAP * base_cd:
        kept = CAP * base_cd
        conv = (base_cd - kept) / max(base_cd - cd10, 0.1)
    else:
        kept = cd10
        conv = 1.0
    cd = base_cd - f * kept
    mult = (1 + f * dmg10) * (1 + f * (conv - 1))
    return max(cd, 0.5), mult


def steps_of(owned):
    """수첩 owned {도술: {br: n}} → {도술: 돌파 단계}"""
    out = {}
    for n, v in (owned or {}).items():
        try:
            s = int((v or {}).get("br") or 0)
        except (TypeError, ValueError, AttributeError):
            s = 0
        if s > 0:
            out[n] = s
    return out
