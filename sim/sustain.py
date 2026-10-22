# 유지력(회복·보호막) 표: 1회량은 공격력 배수(10/21 패치·툴팁, 도술_정보.md 5-2)
# 조건부 회복·보호막은 그 표식을 거는 도술이 트리에 있을 때만 센다(예: 기세 없는 트리의 회전 난격 회복은 0)

# 조건 없는 유지 도술 → 1회량
UNCOND = {"생명의 흐름": 0.60, "생명의 축복": 0.35, "방패 밀기": 0.70, "방패 충격파": 0.35, "강인한 의지": 0.35}
# 받는 도술 → (표식, 1회량)
COND = {"회전 난격": ("기세", 0.10), "날카로운 얼음창": ("기세", 0.10), "연속 찌르기": ("기세", 0.15),
        "찌르기": ("낙인", 0.10), "휘둘러 내려치기": ("낙인", 0.15), "휘둘러치기": ("질풍", 0.15),
        "먹 베기": ("수호", 0.10), "도약 찌르기": ("수호", 0.15)}
# 표식 → 거는 도술
MARK_SRC = {"기세": {"내려치기", "올려치기", "대검 찍기"}, "낙인": {"내려찍기", "약점 베기"},
            "질풍": {"찌르기", "연속 찌르기"}, "수호": {"방패 치기", "방패 내려찍기"}}


def amount(n):
    return UNCOND[n] if n in UNCOND else COND[n][1]


def active(order):
    """트리에서 유지력이 실제로 나오는 도술(순서 유지)"""
    have = set(order)
    return [n for n in order if n in UNCOND or (n in COND and MARK_SRC[COND[n][0]] & have)]


def uncond(order):
    """조건 없는 유지 도술(순서 유지)"""
    return [n for n in order if n in UNCOND]


def count(order):
    """등급(생존·믹스·딜)을 나누는 유지 도술 개수: 조건 없는 것만(10/22 사용자 결정).
    조건부 회복·보호막(낙인·기세 등)은 rate(유지력 수치)에만 들어간다"""
    return len(uncond(order))


def rate(order, casts, seconds):
    """초당 '공격력의 N%'(퍼센트 숫자)"""
    return sum(casts.get(n, 0) * amount(n) for n in active(order)) / seconds * 100
