# 도술 돌파(1~10단계) 효과 — 도깨비지지(kkaebi.gg) 10/14 패치 반영 게임 데이터 표
# data/transcend.json: 도술마다 단계별 누적 피해 증가 %(dmg)와 재사용 대기시간 감소 초(cd). 원본은 data/transcend_kkaebi_gg_raw.txt
# 조건부 추가 효과(예: '감전 대상에게 추가 피해')는 note에만 두고 계산에는 넣지 않는다.
import json, os

T = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "transcend.json"), encoding="utf-8"))


def effect(name, step, base_cd):
    """(새 쿨타임, 피해 배율). 돌파 정보가 없거나 0단계면 (base_cd, 1.0)"""
    t = T.get(name)
    try:
        step = int(step or 0)
    except (TypeError, ValueError):
        step = 0
    if not t or step <= 0 or not base_cd:
        return base_cd, 1.0
    step = min(step, len(t["dmg"]))
    cd = base_cd - t["cd"][step - 1]
    return max(cd, 0.5), 1 + t["dmg"][step - 1] / 100.0


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
