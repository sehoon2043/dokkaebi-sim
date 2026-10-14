# 요약을 사이트의 community.json 에 반영하고 수집 위치(meta)를 갱신한다
#   python tools/community/publish.py <entry.json> <collect 출력.meta.json> <사이트 community.json>
# entry.json: {"range": "10/14 16:51~19:55", "headline": "한 줄", "sections": [{"h": "제목", "items": ["...", ...]}, ...],
#              "summary": {"range": "10/14 14:36~19:55", "headline": "...", "sections": [{"h": "...", "items": [{"k": "공식", "t": "..."}, ...]}]}}
#   - 맨 위 필드: 이번 구간 기록(entries 맨 앞에 추가)
#   - summary: 지금까지를 합친 요약(통째로 교체). 디시 글 수·공지 수는 여기서 누적
import json, sys, datetime as dt

KEEP = 18   # 4시간마다면 약 3일치
KINDS = {"공식", "제보", "의견", "주의"}
entry, meta_new, site = sys.argv[1], sys.argv[2], sys.argv[3]
e = json.load(open(entry, encoding="utf-8"))
m = json.load(open(meta_new, encoding="utf-8"))
sm = e.pop("summary", None)

def check(secs):
    assert isinstance(secs, list) and secs, "sections 비어 있음"
    for s in secs:
        assert s.get("h") and isinstance(s.get("items"), list), "섹션 형식 오류"
        for it in s["items"]:
            if isinstance(it, dict):
                assert it.get("t") and it.get("k", "의견") in KINDS, "항목 형식 오류: " + json.dumps(it, ensure_ascii=False)

check(e.get("sections"))
if sm:
    check(sm.get("sections"))
try:
    d = json.load(open(site, encoding="utf-8"))
except Exception:
    d = {"meta": {}, "entries": []}
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
e["at"] = now.strftime("%m/%d %H:%M")
e["counts"] = {"dc": m.get("dc_new", 0), "forum": m.get("forum_new", 0)}
old = d.get("entries", [])
d["entries"] = [e] + old[:KEEP - 1]
if sm:
    prev = (d.get("summary") or {}).get("counts")
    if prev is None:
        prev = {"dc": sum(x.get("counts", {}).get("dc", 0) for x in old), "forum": sum(x.get("counts", {}).get("forum", 0) for x in old)}
    sm["at"] = e["at"]
    sm["counts"] = {"dc": prev.get("dc", 0) + e["counts"]["dc"], "forum": prev.get("forum", 0) + e["counts"]["forum"]}
    d["summary"] = sm
d["meta"] = {"last_dc": m["last_dc"], "last_forum": m["last_forum"], "updated": now.strftime("%Y-%m-%d %H:%M")}
open(site, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1) + "\n")
print("ok", e["at"], len(d["entries"]), "summary" if sm else "")
