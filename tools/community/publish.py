# 요약 한 건을 사이트의 community.json 맨 앞에 넣고 수집 위치(meta)를 갱신한다
#   python tools/community/publish.py <entry.json> <collect 출력.meta.json> <사이트 community.json>
# entry.json: {"range": "12:00~16:00", "headline": "한 줄 요약", "sections": [{"h": "제목", "items": ["...", ...]}, ...]}
import json, sys, datetime as dt

KEEP = 18   # 4시간마다면 약 3일치
entry, meta_new, site = sys.argv[1], sys.argv[2], sys.argv[3]
e = json.load(open(entry, encoding="utf-8"))
m = json.load(open(meta_new, encoding="utf-8"))
assert isinstance(e.get("sections"), list) and e["sections"], "sections 비어 있음"
for s in e["sections"]:
    assert s.get("h") and isinstance(s.get("items"), list), "섹션 형식 오류"
try:
    d = json.load(open(site, encoding="utf-8"))
except Exception:
    d = {"meta": {}, "entries": []}
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
e["at"] = now.strftime("%m/%d %H:%M")
e["counts"] = {"dc": m.get("dc_new", 0), "forum": m.get("forum_new", 0)}
d["entries"] = [e] + d.get("entries", [])[:KEEP - 1]
d["meta"] = {"last_dc": m["last_dc"], "last_forum": m["last_forum"], "updated": now.strftime("%Y-%m-%d %H:%M")}
open(site, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
print("ok", e["at"], len(d["entries"]))
