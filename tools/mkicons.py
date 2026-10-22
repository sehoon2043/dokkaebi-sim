# 도술 아이콘: 비공개 기록 폴더의 webp를 사이트 저장소 icons/로 복사하고, 도술 이름 → 파일 이름 표(site/icons.json)를 만든다
#   python tools/mkicons.py <아이콘 폴더> <사이트 저장소 폴더>
#   파일 이름 = data/skills.json 도술 i 경로의 파일 이름(확장자만 webp)
import json, os, shutil, sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
src, site = sys.argv[1], sys.argv[2]
D = json.load(open(os.path.join(ROOT, "data", "skills.json"), encoding="utf-8"))
dst = os.path.join(site, "icons")
os.makedirs(dst, exist_ok=True)
table, miss = {}, []
for k in D["skills"]:
    f = os.path.splitext(os.path.basename(k.get("i") or ""))[0] + ".webp"
    p = os.path.join(src, f)
    if not k.get("i") or not os.path.exists(p):
        miss.append(k["n"])
        continue
    shutil.copyfile(p, os.path.join(dst, f))
    table[k["n"]] = f
json.dump(table, open(os.path.join(ROOT, "site", "icons.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(f"{len(table)}개 복사 · 없음: {', '.join(miss) or '없음'}")
