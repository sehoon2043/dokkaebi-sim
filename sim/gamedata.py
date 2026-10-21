# 계산용 게임 데이터 읽기
#   도술 수치표(skills.json)·돌파 표(transcend.json)는 외부 자료를 정리한 것이라 저장소에 넣지 않는다.
#   data/에 파일이 있으면 그것을 쓰고, 없으면 저장 서버(DOSA_URL·DOSA_KEY)에서 받아 data/에 둔다.
import json, os, urllib.parse, urllib.request

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load(name):
    path = os.path.join(DIR, name)
    if not os.path.exists(path):
        url, key = os.environ.get("DOSA_URL"), os.environ.get("DOSA_KEY")
        if not url or not key:
            raise RuntimeError(f"data/{name}이 없습니다. DOSA_URL·DOSA_KEY 환경 변수로 저장 서버에서 받아야 합니다.")
        q = urllib.parse.urlencode({"a": "data", "name": name, "key": key})
        with urllib.request.urlopen(url + "?" + q, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
        if not j.get("ok"):
            raise RuntimeError(f"저장 서버에서 {name}을 받지 못했습니다: {j.get('err')}")
        os.makedirs(DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(j["value"], f, ensure_ascii=False)
    with open(path, encoding="utf-8") as f:
        return json.load(f)
