# 도술 돌파(1~10단계) 효과 표(10/14 패치 반영)
# transcend.json(gamedata.py로 읽음): 도술마다 단계별 누적 피해 증가 %(dmg)와 재사용 대기시간 감소 초(cd)
# 조건부 추가 효과(예: '감전 대상에게 추가 피해')는 note에만 두고 계산에는 넣지 않는다.
import gamedata

T = gamedata.load("transcend.json")


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
    """수첩 owned {도술: {dp: n}} → {도술: 돌파 단계}
    br은 각성(도술 별 단계)이라 캐릭터 능력치만 오르고 도술 피해·쿨은 그대로다(10/09 사용자 확인) → 계산에 쓰지 않는다.
    돌파(스타일 50강 뒤 1~10단계)는 dp로 받는다(사이트 입력 칸은 아직 없음)."""
    out = {}
    for n, v in (owned or {}).items():
        try:
            s = int((v or {}).get("dp") or 0)
        except (TypeError, ValueError, AttributeError):
            s = 0
        if s > 0:
            out[n] = s
    return out
