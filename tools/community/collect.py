# 커뮤니티 수집: 디시 도깨비의세계 갤러리 새 글 + 공식 포럼 새 공지를 요약하기 좋은 텍스트로 모은다
#   python tools/community/collect.py <community.json> <출력 txt>
#   community.json 의 meta.last_dc(마지막으로 본 디시 글 번호)·meta.last_forum(마지막으로 본 공지 시각, 한국 시간)
#   이후 글만 모은다. 처음이면 최근 4시간 분량.
# 표준 라이브러리만 사용(클라우드 실행용). 요청 사이 쉼을 두고 동시 요청은 3개까지
import json, re, sys, html, time, datetime as dt, urllib.request, concurrent.futures as cf

KST = dt.timezone(dt.timedelta(hours=9))
UA_M = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Mobile Safari/537.36"
UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
DC = "https://m.dcinside.com/board/tokkebiworld"
FB = "https://forum-api.kakaogames.com/v1/dokkaebi/boards"
MAX_PAGES = 100     # 디시 목록 최대 페이지(약 3,000개, 실행이 몇 번 빠져도 놓치지 않게)
MAX_BODIES = 110    # 본문까지 읽을 글 수
KW = re.compile(r"공지|패치|점검|보상|쿠폰|버그|너프|하향|상향|메타|빌드|트리|세팅|덱|절명|파멸|저격|연타|기동|주술|강타|헌신|기만|척살|제압|강인|"
                r"사냥터|황무지|호랑|비경|엽전|레이드|보스|낙화|승천|돌파|강화|각성|영웅|전설|도안|추옵|추가 ?효과|변경권|거래소|정확도|명중|"
                r"평타|치명|효율|시간당|분당|실측|dps|정리|팁|확률|제재|정지|라방|방송", re.I)


def get(u, ua, accept=None):
    h = {"User-Agent": ua, "Referer": "https://m.dcinside.com/" if "dcinside" in u else "https://forum.kakaogames.com/dokkaebi/"}
    if accept:
        h["Accept"] = accept
    for i in range(3):
        try:
            time.sleep(0.4)
            return urllib.request.urlopen(urllib.request.Request(u, headers=h), timeout=20).read().decode("utf-8", "ignore")
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    print(f"[요청 실패] {u} {err}", file=sys.stderr)
    return ""


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


# ---------- 디시 ----------
LI = re.compile(r'tokkebiworld/(\d+)\?[^"]*" class="lt">.*?<span class="subjectin">(.*?)</span>.*?<ul class="ginfo ">(.*?)</ul>.*?<span class="ct ">(\d+)</span>', re.S)


def dc_list(last):
    posts = {}
    for p in range(1, MAX_PAGES + 1):
        h = get(f"{DC}?page={p}", UA_M)
        found = LI.findall(h)
        for n, t, info, c in found:
            lis = [text(x) for x in re.findall(r"<li[^>]*>(.*?)</li>", info, re.S)]
            num = lambda k: int(re.sub(r"\D", "", next((x for x in lis if x.startswith(k)), "0")) or 0)
            posts[int(n)] = {"t": text(t), "v": num("조회"), "r": num("추천"), "c": int(c)}
        if not found or min(int(n) for n, *_ in found) <= last:
            break
    return {n: q for n, q in posts.items() if n > last}


def dc_body(n):
    h = get(f"{DC}/{n}", UA_M)
    m = re.search(r'<div class="thum-txtin">(.*?)</div>\s*</div>', h, re.S)
    body = text(re.sub(r"<script.*?</script>", "", m.group(1) if m else "", flags=re.S))
    cs = [text(c) for c in re.findall(r'<p class="txt">(.*?)</p>', h, re.S)]
    cs = [c for c in cs if c and c != "비밀번호를 입력하세요."]
    d = re.search(r'<li>(\d{4}\.\d{2}\.\d{2} \d{2}:\d{2})</li>', h)
    return n, (d.group(1) if d else ""), body, cs


# ---------- 공식 포럼 ----------
def forum_new(last):
    out = []
    for code in ("notice", "update", "event"):
        try:
            ps = json.loads(get(f"{FB}/{code}/list?page=1", UA_PC, "application/json"))["payload"].get("posts", [])
        except Exception:
            continue
        for it in ps[:12]:
            d = str(it.get("published_at") or it.get("created_at") or "")[:19]
            try:
                k = (dt.datetime.strptime(d, "%Y-%m-%d %H:%M:%S") + dt.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                continue
            if k <= last:
                continue
            try:
                p = json.loads(get(f"{FB}/{code}/posts/{it['post_id']}", UA_PC, "application/json"))["payload"]
                c = text(re.sub(r"<(br|/p|/div|/li)[^>]*>", "\n", p.get("content") or ""))
            except Exception:
                c = ""
            out.append((k, code, it["post_id"], it.get("title", ""), c))
    return sorted(out)


def main():
    meta = {}
    try:
        meta = json.load(open(sys.argv[1], encoding="utf-8")).get("meta", {})
    except Exception:
        pass
    now = dt.datetime.now(KST)
    last_forum = meta.get("last_forum") or (now - dt.timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    last_dc = int(meta.get("last_dc") or 0)
    if not last_dc:
        # 처음: 최신 글 번호에서 대략 4시간 분량(약 800개)만
        first = LI.findall(get(f"{DC}?page=1", UA_M))
        last_dc = max((int(n) for n, *_ in first), default=0) - 800
    posts = dc_list(last_dc)
    top = sorted(posts, key=lambda n: -(posts[n]["r"] * 20 + posts[n]["c"] * 6 + posts[n]["v"] * 0.1 + (80 if KW.search(posts[n]["t"]) else 0)))[:MAX_BODIES]
    with cf.ThreadPoolExecutor(3) as ex:
        bodies = list(ex.map(dc_body, sorted(top)))
    notes = forum_new(last_forum)
    out = open(sys.argv[2], "w", encoding="utf-8")
    w = lambda s="": out.write(s + "\n")
    w(f"# 수집 시각 {now:%Y-%m-%d %H:%M} (한국 시간)")
    w(f"# 디시: 글 번호 {last_dc + 1} 이후 새 글 {len(posts)}개 중 반응 많은 {len(bodies)}개 본문·댓글")
    w(f"# 공식 포럼: {last_forum} 이후 새 글 {len(notes)}개")
    w()
    w("## 공식 포럼 새 글")
    for k, code, pid, t, c in notes:
        w(f"### [{code} {pid} {k}] {t}\n{c[:6000]}\n")
    if not notes:
        w("(없음)\n")
    w("## 디시 갤러리 (글번호 시각 추천 댓글 | 제목 :: 본문 || 댓글)")
    for n, d, body, cs in bodies:
        q = posts[n]
        w(f"[{n} {d[11:]} 추{q['r']} 댓{q['c']}] {q['t']} :: {body[:500]} || {' / '.join(cs)[:600]}")
    out.close()
    newest = max(posts, default=last_dc)
    newest_forum = max([k for k, *_ in notes], default=last_forum)
    json.dump({"last_dc": newest, "last_forum": newest_forum, "dc_new": len(posts), "dc_read": len(bodies), "forum_new": len(notes)},
              open(sys.argv[2] + ".meta.json", "w", encoding="utf-8"), ensure_ascii=False)
    print(f"디시 새 글 {len(posts)} (본문 {len(bodies)}), 포럼 새 글 {len(notes)} → {sys.argv[2]}")


if __name__ == "__main__":
    main()
