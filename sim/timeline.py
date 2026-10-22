# 도술 시전 시간표 시뮬레이터 (자체 작성, 10/16)
#   자동 사냥 규칙: 지금 쓸 수 있는 도술 중 '사용 순서'가 가장 앞선 것을 쓴다. 쓸 도술이 없으면 평타를 치거나 기다린다.
#   도술 수치(쿨타임·동작 시간·피해 계수·충전 수)는 skills.json(0강 값, gamedata.py로 읽음),
#   스타일 신식 효과는 인게임 신식 개방 설명과 허수아비·비경 실측(도술_정보.md)에서 정한 값이다.
#   보정값(평타, 도술 사이 딜레이, 저격·암습 보정, 검의 형상 쿨 감소)은 field.py가 실측에 맞춰 넣는다.
import math
import gamedata

D = gamedata.load("skills.json")
ST = [s["n"] for s in D["styles"]]
BY = {k["n"]: k for k in D["skills"]}
ULT_OF = {ST[k["st"]]: k["n"] for k in D["skills"] if k["u"]}

# ---------- 바꿔 가며 계산하는 값(field.py·verify.py가 고침) ----------
AMP_HIT = {"파멸/요혼격": 0.10, "저격/꿰뚫는 저격": 0.10, "기만/공간 결계": 0.10}   # 적중 뒤 받는 피해 증가(겹치지 않고 큰 값)
AMP_SEC = 5
CD_RED = 6               # 절명: 검의 형상이 가득 찬 상태에서 더 얻으면 궁극기 쿨타임 감소(초)
FORMS_PER_CAST = True    # 절명: 검의 형상을 도술 1회당 1개(실측과 맞음). False면 타수만큼
FORMS_STYLE_ONLY = False # 절명: 절명 도술로만 검의 형상을 얻음
STRICT_MAX = True        # 절명: 이미 가득 찬 상태에서 얻을 때만 쿨 감소
BASIC = 0.0              # 평타 1회 피해(모델 단위). 0이면 평타 없이 기다림
BASIC_I = 0.7            # 평타 1회 동작(초)
SYN = True               # 상태 이상 연계 계산 여부
ARM = 0.05               # 방어력 10% 감소 = 피해 +5%로 가정

BUFF_DMG = {"헌신/용맹의 기운": ("공격력 증가", 0.112, 10)}   # 10/21: 최후의 저항 피해 증가 삭제, 용맹의 기운은 공격력 +11.2%
BUFF_CD = {"헌신/개전의 가호": 0.10}
BUFF_CD_SEC = 10
# 주술 궁극기 신내림(10/21 툴팁): 179.1% × 6회 + 약화 [강화 저주] 중첩당 7%/초(5초), 5중첩이면 반경 3m 최대 5명에게 358.2% 폭발 후 중첩 초기화.
#   6회 타격 중 5번째에 폭발, 남은 1중첩이 5초 동안 7%씩 → 대상마다 (폭발, 지속 피해) = (358.2, 35)
#   주술 신식 3단계 구슬 보너스(+30/60/90%)는 이 강화 저주·폭발에만 붙고 직접 피해에는 안 붙는다(툴팁)
CURSE = {"신내림": (358.2, 7.0 * 5)}
# 저격 궁극기(정조준): 덱에 있는 상태 이상 종류(출혈·화상·감전·약화) 하나마다 피해 +15%
STATUS_BY = [["절명/환영 참격", "기동/급소 관통"], ["저격/폭발하는 화살", "파멸/화염구", "파멸/하늘의 심판"], ["파멸/번개 폭풍", "기동/일섬"],
             ["주술/살 날리기", "주술/부적 던지기"]]

# ---------- 상태 이상 연계 (도술 설명 기준) ----------
DUR = {"동상": 5, "파쇄": 5, "저주": 15}     # 지속 시간(사용자 확인), 나머지는 10초
DUR_DEFAULT = 10
COND = {"사격": ("파쇄", 1 / 3), "쇠뇌 사격": ("동상", 1 / 3), "약점 베기": ("기운", 1 / 3), "얼음화살": ("기운", 1 / 3),
        "심장 절단": ("출혈", 0.23), "삼단 찌르기": ("충격", 1 / 3)}   # 10/21: 대부분 '추가 피해 1회'(계수 합의 1/3)로 바뀜   # 대상이 그 상태면 피해 증가. 마비·빙결은 보스 면역이라 뺌
APPLY = {"내려찍기": ["낙인"], "약점 베기": ["낙인"], "삼단 찌르기": ["관통"], "환영 참격": ["출혈"], "급소 관통": ["출혈"],
         "주먹 지르기": ["충격"], "연속 충격": ["충격"], "휘둘러 내려치기": ["파쇄"], "회전 난격": ["파쇄"], "휘둘러치기": ["파쇄"],
         "크게 베기": ["파열"], "검기 날리기": ["파열"], "얼음화살": ["동상"], "날카로운 얼음창": ["동상"],
         "폭발하는 화살": ["화상"], "화염구": ["화상"], "하늘의 심판": ["화상"], "번개 폭풍": ["감전"], "일섬": ["감전"],
         "부적 던지기": ["약화"], "살 날리기": ["약화"]}
DOT = {"출혈": 2.0, "화상": 2.0, "감전": 2.0}   # 지속 피해(모델 단위/초). 10/21: 공격력 5% → 2%, 주술 저주 지속 피해 삭제
SELF_ELEM = {"낙뢰", "화염 분출", "붕괴하는 대지", "연쇄 번개"}  # 쓰면 대상에 [기운](원소) 10초
VULN = {"내려찍기": [("파열", "받피5a")], "내려치기": [("파열", "받피5a")], "화염 분출": [("파쇄", "받피5b")], "연쇄 번개": [("파쇄", "받피5b")],
        "낙뢰": [("관통", "방깎5")], "올려치기": [("관통", "방깎5")]}   # 대상이 앞 상태면 새 디버프(10초)
VULN_GAIN = {"받피5a": 0.10, "받피5b": 0.10}   # 10/21: 파열·파쇄 받는 피해 5% → 10%
ARMOR_SRC = {"연쇄 타격", "영혼 소용돌이"}   # 방어력 10% 감소 5초
# 차지 도술 단계 수(10/21 공지). 피해 계수는 최대 차지 기준이라 차지 시간(cm × (단계 - 1))을 동작 시간에 더한다
CHARGE_STAGES = {"크게 베기": 2, "연속 충격": 3, "검기 날리기": 4, "대검 강타": 4, "검기 폭발": 4, "천벌": 4, "일점 저격": 3}


def charge_time(name, num):
    st = CHARGE_STAGES.get(name, 1)
    return (st - 1) * (num.get("cm") or 0) / 1000 if st > 1 else 0.0


# ---------- 도술 데이터 ----------
def lvcoef(k, levels):
    """스타일 강화 레벨에 따른 피해 계수 증가(0.0 = 0강)"""
    L = levels.get(ST[k["st"]], levels.get("*", 1))
    if not L:
        return 0.0
    return next((x["coefficient"] for x in k["num"]["lv"] if x["level"] == L), 0.0)


def total(k):
    """도술 1회 총 피해 계수(0강)"""
    n = k["num"]
    if n["total"]:
        return n["total"]
    if n["dc"]:
        last = n["dc"][-1]
        return last["basic_coefficient"] * (last["hits"] or 1)
    return 0


def bottom_styles(names):
    """하단 5칸의 스타일별 개수(궁극기 제외)"""
    c = {}
    for n in names[:5]:
        s = ST[BY[n]["st"]]
        c[s] = c.get(s, 0) + 1
    return c


def ult_for(names):
    """하단 5칸에 같은 스타일이 3개 이상이면 그 스타일 궁극기. 여럿이면 개수 많은 쪽, 같으면 먼저 놓인 쪽"""
    c = bottom_styles(names)
    first = {}
    for i, n in enumerate(names[:5]):
        first.setdefault(ST[BY[n]["st"]], i)
    ok = sorted((s for s in c if c[s] >= 3 and s in ULT_OF), key=lambda s: (-c[s], first[s]))
    return ULT_OF[ok[0]] if ok else None


def build(names, levels, overhead):
    """칸 이름 목록 → (궁극기, 구성원, 쓸 도술 목록). 쓸 도술: 피해·쿨이 있는 도술만"""
    u = ult_for(names)
    members, order = [], []
    for n in list(names) + ([u] if u else []):
        k = BY[n]
        nm = k["num"]
        m = {"id": k["id"], "n": n, "style": ST[k["st"]], "u": bool(k["u"]),
             "hits": sum((c["hits"] or 1) for c in nm["dc"]) or 1, "stacks": k["ms"] or 1}
        members.append(m)
        base = total(k) + sum(CURSE.get(n, ()))
        if n in CURSE:
            m["orb_frac"] = sum(CURSE[n]) / base   # 구슬 보너스가 붙는 몫(강화 저주·폭발)
        dmg = base * (1 + lvcoef(k, levels))
        if dmg > 0 and nm["cd"] > 0:
            order.append(dict(m, damage=dmg, cd=nm["cd"], motion=(nm["pm"] or 0) + nm["m"] / 1000 + charge_time(n, nm) + overhead))
    return u, members, order


# ---------- 스타일 신식 (하단 5칸에 그 스타일 3개 이상일 때 켜짐) ----------
class Shinsik:
    def tick(self, sim, dt):                 # 시간이 흐를 때
        pass

    def bonus(self, sim, sk):                # 이번 시전 피해 배율
        return 1.0

    def after(self, sim, sk, start, end):     # 시전이 끝난 뒤
        pass


class Rage(Shinsik):            # 연타: 적중 타수만큼 격노(최대 50), 3초 적중 없으면 초기화, 격노 1당 피해 +0.4%
    def __init__(self):
        self.v, self.last = 0, None

    def bonus(self, sim, sk):
        if self.last is not None and sim.now - self.last > 3:
            self.v = 0
        return 1 + 0.004 * self.v

    def after(self, sim, sk, start, end):
        self.v = min(50, self.v + sk["hits"])
        self.last = end


class Overflow(Shinsik):        # 파멸: 시전마다 영력 10(최대 200) → 요기범람 30초: 피해 +10%, 일반 도술 쿨 초기화 (10/21: 전개 속도·보호막 삭제)
    GAIN, FULL, SEC = 10, 200, 30

    def __init__(self):
        self.g, self.until = 0, -1.0

    def bonus(self, sim, sk):
        return 1.10 if sim.now < self.until else 1.0

    def after(self, sim, sk, start, end):
        if end < self.until:
            return
        self.g += self.GAIN
        if self.g >= self.FULL:
            self.g = 0
            self.until = end + self.SEC
            for s in sim.skills:
                if not s["u"]:
                    s["charges"], s["ready_at"] = s["stacks"], None


class Charge(Shinsik):          # 강타: 시전마다 영력 10(최대 100), 33/66/100에서 피해 +3/7/10%. 가득 찬 채 궁극기를 쓰면 [강압]: 일반 도술 쿨 초기화(10/21)
    def __init__(self):
        self.v = 0

    def bonus(self, sim, sk):
        return 1.10 if self.v >= 100 else 1.07 if self.v >= 66 else 1.03 if self.v >= 33 else 1.0

    def after(self, sim, sk, start, end):
        if sk["u"] and self.v >= 100:
            self.v = 0
            for s in sim.skills:
                if not s["u"]:
                    s["charges"], s["ready_at"] = s["stacks"], None
            return
        self.v = min(100, self.v + 10)


class Locks(Shinsik):           # 제압: 시전마다 자물쇠 1(최대 3), 자물쇠 1개당 피해 +2%·궁극기 쿨 3초 감소, 궁극기가 1개 소모(10/21)
    def __init__(self):
        self.v = 0

    def bonus(self, sim, sk):
        return 1 + 0.02 * min(3, self.v)

    def after(self, sim, sk, start, end):
        if sk["u"]:
            if sk["ready_at"] is not None:
                sk["ready_at"] = max(end, sk["ready_at"] - 3 * min(3, self.v))
            self.v = max(0, self.v - 1)
            return
        self.v = min(3, self.v + 1)


class Execute(Shinsik):         # 척살(10/21): 시전마다 영력 3(최대 100, 처치는 계산 안 함) → 척결 1중첩(최대 10): 피해 +2%, 남은 쿨 20%(궁 10%) 감소
    def __init__(self):
        self.g, self.v = 0, 0

    def bonus(self, sim, sk):
        return 1 + 0.02 * min(10, self.v)

    def after(self, sim, sk, start, end):
        self.g += 3
        if self.g >= 100:
            self.g = 0
            self.v = min(10, self.v + 1)
            for s in sim.skills:
                if s["ready_at"] is not None:
                    left = s["ready_at"] - end
                    if left > 0:
                        s["ready_at"] = end + left * (0.9 if s["u"] else 0.8)


class Daggers(Shinsik):         # 절명: 시전(또는 타수)마다 검의 형상(최대 5), 궁극기가 전량 소모해 3/4/5개면 +55/75/125%,
    BONUS = {3: 0.55, 4: 0.75, 5: 1.25}   # 형상이 가득 찬 상태에서 '도술 최초 시전 시' 궁극기 쿨 감소(10/21).
    PER_SKILL_ONCE = True                 # 해석: 형상이 가득 찬 동안 도술마다 처음 한 번만 감소, 궁극기를 쓰면 다시. 실측으로 확인 필요

    def __init__(self):
        self.v = 0
        self.used = set()

    def bonus(self, sim, sk):
        return 1 + self.BONUS.get(min(5, self.v), 0.0) if sk["u"] and self.v >= 3 else 1.0

    def after(self, sim, sk, start, end):
        if sk["u"]:
            self.v = 0
            self.used = set()
            return
        if sk["damage"] <= 0 or (FORMS_STYLE_ONLY and sk["style"] != "절명"):
            return
        full_before = self.v >= 5
        self.v = min(5, self.v + (1 if FORMS_PER_CAST else sk["hits"]))
        if self.v >= 5 and (full_before or not STRICT_MAX):
            if self.PER_SKILL_ONCE:
                if sk["n"] in self.used:
                    return
                self.used.add(sk["n"])
            for s in sim.skills:
                if s["u"] and s["ready_at"] is not None:
                    s["ready_at"] = max(end, s["ready_at"] - CD_RED)


class Arrows(Shinsik):          # 저격: 1초에 영력 25 → 100마다 화살촉(최대 3). 화살촉 있으면 저격 외 도술 +5%/개,
    def __init__(self):         # 저격 도술이 3개를 모두 소모하면 +45%
        self.g, self.n, self.aim, self.spend = 0.0, 0, -1.0, False

    def tick(self, sim, dt):
        self.g += 25 * dt
        while self.g >= 100 and self.n < 3:
            self.g -= 100
            self.n += 1
        if self.n >= 3:
            self.g = min(self.g, 100)

    def bonus(self, sim, sk):
        m = 1.0
        self.spend = sk["style"] == "저격" and self.n >= 3
        if self.spend:
            m *= 1.45
        elif sk["style"] != "저격" and self.n:
            m *= 1 + 0.05 * self.n     # 10/21: 저격 외 도술 +5%/개, [조준](+10%) 삭제
        return m

    def after(self, sim, sk, start, end):
        if self.spend:
            self.n, self.aim, self.spend = 0, end + 10, False


class Orbs(Shinsik):            # 주술(10/21): 시전마다 영력 8(최대 100) → 30/60/90에서 구슬 1/2/3. 궁극기의 강화 저주·폭발 +30/60/90%(툴팁),
    def __init__(self):         # 구슬이 있을 때 주술 도술을 쓰면 궁극기 포함 모든 도술 남은 쿨 0.1초×구슬 감소
        self.g = 0

    def orbs(self):
        return 3 if self.g >= 90 else 2 if self.g >= 60 else 1 if self.g >= 30 else 0

    def bonus(self, sim, sk):
        o = self.orbs()
        # 직접 피해에는 안 붙으므로 강화 저주·폭발 몫(orb_frac)만큼만 올린다
        return 1 + (0.90, 0.60, 0.30)[3 - o] * sk.get("orb_frac", 0.0) if sk["u"] and o else 1.0

    def after(self, sim, sk, start, end):
        self.g = min(100, self.g + 8)
        o = self.orbs()
        if o and sk["style"] == "주술":
            for s in sim.skills:
                if s["ready_at"] is not None:
                    s["ready_at"] = max(end, s["ready_at"] - 0.1 * o)


class Dash(Shinsik):            # 기동: 시전마다 영력 10(최대 200, 10/21) → 궁극기 쿨 초기화와 [연쇄] 10초(궁극기 피해 +50%, 툴팁 확인)
    def __init__(self):
        self.g, self.until = 0, -1.0

    def bonus(self, sim, sk):
        return 1.5 if sk["u"] and sim.now < self.until else 1.0

    def after(self, sim, sk, start, end):
        self.g += 10
        if self.g >= 200:
            self.g, self.until = 0, end + 10
            for s in sim.skills:
                if s["u"] and s["ready_at"] is not None:
                    s["ready_at"] = end


class Tears(Shinsik):           # 기만: 시전마다 눈물 1(최대 2), 2개가 되면 방금 쓴 일반 도술 쿨 절반
    def __init__(self):
        self.v = 0

    def after(self, sim, sk, start, end):
        self.v = min(2, self.v + 1)
        if self.v >= 2 and not sk["u"] and sk["ready_at"] is not None:
            sk["ready_at"] = start + max(sim.cd_of(sk, start) * 0.5, sk["motion"])
            self.v = 0


SHINSIK = {"연타": Rage, "파멸": Overflow, "강타": Charge, "제압": Locks, "척살": Execute,
           "절명": Daggers, "저격": Arrows, "주술": Orbs, "기동": Dash, "기만": Tears}
# 계산 순서(피해 배율은 곱이라 순서와 무관, 시전 뒤 처리는 이 순서로)
SHINSIK_ORDER = ["저격", "연타", "파멸", "기만", "주술", "기동", "강타", "제압", "척살", "절명"]


# ---------- 시뮬레이터 ----------
class Sim:
    def __init__(self, order, members, horizon, events=None):
        self.skills = order
        self.horizon = horizon
        self.events = events
        self.now = 0.0
        self.total = 0.0
        for s in order:
            s["charges"], s["ready_at"] = s["stacks"], None
        bot = bottom_styles([m["n"] for m in members if not m["u"]])
        self.sh = [SHINSIK[st]() for st in SHINSIK_ORDER if bot.get(st, 0) >= 3]
        self.over = next((x for x in self.sh if isinstance(x, Overflow)), None)
        self.n_status = sum(1 for g in STATUS_BY if any(m["style"] + "/" + m["n"] in g for m in members))
        self.amp = (0.0, -1.0)          # (값, 끝나는 시각)
        self.buffs = {}                 # 이름: (값, 끝)
        self.cdcut = (0.0, -1.0)
        self.debuff = {}                # 대상에 걸린 상태: 끝나는 시각
        self.casts = {}                 # 도술별 시전 횟수(유지력 계산용)

    def fast(self):
        return False   # 10/21: 요기범람 전개 속도 50% 증가 삭제

    def motion(self, s):
        return s["motion"] / 1.5 if self.fast() else s["motion"]

    def cd_of(self, s, at):
        cut, end = self.cdcut
        return s["cd"] * (1 - cut) if cut and at < end and not s["u"] else s["cd"]

    def add(self, dmg):
        self.total += dmg
        if self.events is not None:
            self.events.append((self.now, dmg))

    def refill(self):
        for s in self.skills:
            while s["ready_at"] is not None and s["ready_at"] <= self.now + 1e-9 and s["charges"] < s["stacks"]:
                s["charges"] += 1
                s["ready_at"] = None if s["charges"] >= s["stacks"] else s["ready_at"] + s["cd"]

    def pick(self):
        for s in self.skills:
            if s["charges"] > 0 and self.now + self.motion(s) <= self.horizon + 1e-9:
                return s
        return None

    def wait(self):
        nxt = [s["ready_at"] for s in self.skills if s["ready_at"] is not None and s["ready_at"] > self.now]
        if not nxt:
            return False
        t = min(nxt)
        if BASIC:
            k = max(1, math.ceil((min(t, self.horizon) - self.now) / BASIC_I - 1e-9))
            self.add(BASIC * k)
            self.now += k * BASIC_I
        else:
            self.now = t
        return True

    def mult(self, s):
        m = 1.0
        for x in self.sh:
            m *= x.bonus(self, s)
        if self.now < self.amp[1]:
            m *= 1 + self.amp[0]
        if s["u"] and s["style"] == "저격":
            m *= 1 + 0.15 * self.n_status
        g = sum(v for v, end in self.buffs.values() if self.now < end)
        if g:
            m *= 1 + g
        if SYN:
            c = COND.get(s["n"])
            if c and self.debuff.get(c[0], -1) > self.now:
                m *= 1 + c[1]
            vul = 1 + sum(v for k, v in VULN_GAIN.items() if self.debuff.get(k, -1) > self.now)
            vul += ARM * (self.debuff.get("방깎", -1) > self.now) + ARM * (self.debuff.get("방깎5", -1) > self.now)
            m *= vul
        return m

    def apply_effects(self, s, start, end):
        if not SYN:
            return
        n = s["n"]
        for need, eff in VULN.get(n, ()):
            if self.debuff.get(need, -1) > start:
                self.debuff[eff] = end + 10
        for x in APPLY.get(n, ()):
            until = end + DUR.get(x, DUR_DEFAULT)
            if x in DOT:   # 지속 피해: 이미 걸린 구간은 겹쳐 세지 않음
                self.total += DOT[x] * max(0.0, min(until, self.horizon) - max(end, self.debuff.get(x, -1)))
            self.debuff[x] = until
        if n in SELF_ELEM:
            self.debuff["기운"] = end + 10
        if n in ARMOR_SRC:
            self.debuff["방깎"] = end + 5

    def cast(self, s):
        self.casts[s["n"]] = self.casts.get(s["n"], 0) + 1
        start = self.now
        self.add(s["damage"] * self.mult(s))
        s["charges"] -= 1
        cd = self.cd_of(s, start)
        if s["ready_at"] is None:
            s["ready_at"] = start + max(cd, s["motion"])
        self.now = start + self.motion(s)
        end = self.now
        self.apply_effects(s, start, end)
        for x in self.sh:
            if not isinstance(x, Daggers):
                x.after(self, s, start, end)
        key = s["style"] + "/" + s["n"]
        if key in AMP_HIT:
            v, until = self.amp
            self.amp = (max(v if end < until else 0.0, AMP_HIT[key]), end + AMP_SEC)
        if key in BUFF_DMG:
            name, v, sec = BUFF_DMG[key]
            self.buffs[name] = (v, end + sec)
        if key in BUFF_CD:
            self.cdcut = (BUFF_CD[key], end + BUFF_CD_SEC)
        for x in self.sh:
            if isinstance(x, Daggers):
                x.after(self, s, start, end)

    def run(self):
        last = 0.0
        for _ in range(20000):
            if self.now >= self.horizon - 1e-9:
                break
            self.refill()
            if self.now > last:
                for x in self.sh:
                    x.tick(self, self.now - last)
                last = self.now
            s = self.pick()
            if s is None:
                if not self.wait():
                    break
                continue
            self.cast(s)
        return self.total / self.horizon


EV = []


def run(order, members, horizon):
    """초당 피해(모델 단위)"""
    return Sim(order, members, horizon).run()


def run_ev(order, members, horizon):
    """run과 같고, 피해가 들어간 시각·양을 EV에 남긴다(필드 처치 속도 계산용)"""
    return Sim(order, members, horizon, EV).run()


def simulate(names, horizon=120, levels={"*": 1}, overhead=0.0, optimize=True):
    """칸 이름 목록으로 바로 계산(테스트용). 순서는 피해/동작 순에서 두 개씩 바꿔 보며 다듬는다"""
    u, members, order = build(names, levels, overhead)
    order.sort(key=lambda a: (-a["damage"] / a["motion"], a["id"]))
    best = run([dict(v) for v in order], members, horizon)
    if optimize:
        for _ in range(3):
            better = False
            for i in range(len(order)):
                for j in range(i + 1, len(order)):
                    t = order[:]
                    t[i], t[j] = order[j], order[i]
                    v = run([dict(x) for x in t], members, horizon)
                    if v > best + 1e-9:
                        order, best, better = t, v, True
            if not better:
                break
    return best, [v["n"] for v in order], u
