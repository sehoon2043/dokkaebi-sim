# 공개 수첩(브라우저 저장판) → GitHub Pages 사이트(구글 시트 저장 + 자동 분석 결과 표시)
#   python tools/mksite.py <공개 수첩 html> <출력 index.html> <Apps Script 웹 앱 URL>
import sys

src, out, api = sys.argv[1], sys.argv[2], sys.argv[3]
h = open(src, encoding="utf-8").read()


def rep(a, b, n=1):
    global h
    c = h.count(a)
    assert c == n, (a[:70], c)
    h = h.replace(a, b)


# 머리 띠: 닉네임·비밀번호
rep('<h1>도사 수첩</h1>',
    '<h1>도사 수첩</h1>\n    <span class="auth"><input id="nick" placeholder="닉네임" maxlength="16" autocomplete="nickname">'
    '<button type="button" id="loadBtn">불러오기</button></span>')
rep('.bar .status{','.auth{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.auth input{width:120px}\n.bar .status{')

# 패치노트: 버튼 + 창. 내용은 patchnotes.json(사이트 저장소)만 고치면 바뀜
rep('<button class="primary" id="saveBtn" type="button">저장</button>',
    '<button class="primary" id="saveBtn" type="button">저장</button>\n    <button type="button" id="pnBtn" class="pn-btn">패치노트<span class="pn-dot" id="pnDot" hidden></span></button>'
    '\n    <button type="button" id="cmBtn" class="pn-btn">커뮤니티 소식<span class="pn-dot" id="cmDot" hidden></span></button>')
rep('  <div class="cols">',
    '  <dialog id="pnDlg" aria-labelledby="pnTitle"><div class="pn-head"><h2 id="pnTitle">패치노트</h2>'
    '<button type="button" id="pnClose" aria-label="닫기">닫기</button></div><div id="pnBody">불러오는 중…</div></dialog>\n'
    '  <dialog id="cmDlg" class="pn-dlg" aria-labelledby="cmTitle"><div class="pn-head"><h2 id="cmTitle">커뮤니티 소식</h2>'
    '<button type="button" id="cmClose" aria-label="닫기">닫기</button></div><div id="cmBody">불러오는 중…</div></dialog>\n\n  <div class="cols">')
rep('.bar .status{',
    '.pn-btn{position:relative}.pn-dot{position:absolute;top:-3px;right:-3px;width:9px;height:9px;border-radius:50%;background:var(--warn)}\n'
    '#pnDlg,#cmDlg{width:min(600px,calc(100vw - 32px));max-height:80vh;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink);padding:0}\n'
    '#pnDlg::backdrop,#cmDlg::backdrop{background:rgba(0,0,0,.45)}\n#cmBody{padding:4px 16px 16px}\n'
    '.cm-hl{margin:0 0 8px;font-weight:600}.cm-sec{margin-top:8px}.cm-sec h4{margin:0 0 4px;font-size:.9rem;color:var(--accent)}\n'
    '.cm-note{font-size:.8rem;color:var(--muted);margin-top:10px}\n'
    '.pn-head{position:sticky;top:0;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 16px;background:var(--panel);border-bottom:1px solid var(--line)}\n'
    '.pn-head h2{margin:0;font-size:1.1rem}\n#pnBody{padding:4px 16px 16px}\n'
    '.pn-ver{padding-block:12px;border-bottom:1px solid var(--line)}.pn-ver:last-child{border-bottom:0}\n'
    '.pn-ver h3{margin:0 0 6px;font-size:.98rem}.pn-ver h3 small{color:var(--muted);font-weight:400;margin-left:6px}\n'
    '.pn-ver ul{margin:0;padding-left:18px;display:grid;gap:3px;font-size:.9rem}\n'
    '.bar .status{')

# 계산에 쓰지 않는 캐릭터 능력치 칸은 숨김(저장된 값은 그대로 둠)
rep('<button type="button" data-go="sec-stats">능력치</button>', '')
rep('  <section id="sec-stats">', '  <section id="sec-stats" hidden>')
rep('<button type="button" data-go="sec-logs">실측 기록</button>', '')
rep('<button type="button" data-go="sec-memo">메모</button>', '')
rep('  <section id="sec-logs">', '  <section id="sec-logs" hidden>')
rep('  <section id="sec-memo">', '  <section id="sec-memo" hidden>')

# 입력 중에는 이 브라우저에 임시 저장, 서버 저장은 저장 버튼으로만
rep('timer = setTimeout(save, 1500); }', 'timer = setTimeout(saveDraft, 1200); }')
rep('function changed(){ dirty = true; setStatus("저장 안 됨");',
    'function changed(){ dirty = true; setStatus(auth ? "저장 안 됨 · 저장을 눌러야 분석에 반영돼요" : "저장 안 됨");')

a = h.index('const LS = "dosa-notebook-public-v1";')
b = h.index('function barH(){')
h = h[:a] + r'''const LS = "dosa-notebook-site-v1", LSA = "dosa-notebook-site-auth";
const API = "__API__";
let auth = null, myRes = null;
function saveDraft(){ try { localStorage.setItem(LS, JSON.stringify(state)); } catch (e) {} }
async function api(params, body){
  const r = body ? await fetch(API, {method: "POST", body: JSON.stringify(body)}) : await fetch(API + "?" + new URLSearchParams(params));
  return r.json();
}
// 닉네임만으로 저장·불러오기(길드원 전용). 서버 호환을 위해 비밀번호 칸은 고정값을 보낸다
const PIN = "0000";
const ERR = {input: "닉네임을 입력하세요", size: "내용이 너무 길어요(메모·기록을 줄여 주세요)", pin: "이 닉네임은 다른 방식으로 등록돼 있어요. 다른 닉네임을 쓰세요"};
function cred(){
  const nick = $("nick").value.trim();
  if (!nick) { setStatus(ERR.input, "warn"); return null; }
  return {nick, pin: PIN};
}
function applyResult(res){
  myRes = res && res.trees && res.trees.length ? res : null;
  RECS = myRes || EXAMPLE_RECS; recActive = 0; recConfirm = null;
  renderRight();
}
function remember(c){ auth = c; try { localStorage.setItem(LSA, JSON.stringify({nick: c.nick})); } catch (e) {} }
async function load(c){
  setStatus("불러오는 중…");
  try {
    const r = await api({a: "load", nick: c.nick, pin: c.pin});
    if (!r.ok && r.err === "none") { remember(c); setStatus("새 닉네임이에요. 정보를 입력하고 저장을 누르면 등록돼요", "ok"); return; }
    if (!r.ok) { setStatus(ERR[r.err] || "불러오기 실패", "warn"); return; }
    remember(c);
    state = tidy(normalize(r.data || {})); dirty = false; renderAll();
    applyResult(r.result);
    const pending = !r.result || String(r.resultFor) !== String(r.updatedAt);
    setStatus(c.nick + " 불러옴" + (pending ? " · 마지막 저장 내용을 분석하는 중이에요(2~3분)" : " · 추천 트리가 최신이에요"), "ok");
  } catch (e) { setStatus("서버에 연결하지 못했어요. 잠시 뒤 다시 시도하세요", "warn"); }
}
async function save(){
  if (saving) return;
  const typed = $("nick").value.trim();
  const c = typed ? {nick: typed, pin: PIN} : auth;
  if (!c) { setStatus("닉네임을 먼저 입력하세요", "warn"); return; }
  saving = true; setStatus("저장 중…");
  try {
    const r = await api(null, {a: "save", nick: c.nick, pin: c.pin, data: JSON.parse(JSON.stringify(state)), create: true});
    if (!r.ok) {
      setStatus(ERR[r.err] || "저장 실패", "warn");
    } else {
      remember(c); dirty = false; saveDraft();
      setStatus((r.created ? "등록 완료" : "저장됨") + " · 2~3분 뒤 추천 트리가 갱신돼요", "ok");
      poll(c, r.updatedAt, 0);
    }
  } catch (e) { setStatus("서버에 연결하지 못했어요. 잠시 뒤 다시 저장하세요", "warn"); }
  saving = false;
}
let pollT = null;
function poll(c, upd, n){
  clearTimeout(pollT);
  if (n >= 16) { setStatus("분석이 늦어지고 있어요. 조금 뒤 '불러오기'를 눌러 보세요", "warn"); return; }
  pollT = setTimeout(async () => {
    try {
      const r = await api({a: "load", nick: c.nick, pin: c.pin});
      if (r.ok && String(r.resultFor) === String(upd)) {
        applyResult(r.result); rightTab = "recs"; renderRight();
        setStatus("추천 트리가 갱신됐어요", "ok"); return;
      }
    } catch (e) {}
    poll(c, upd, n + 1);
  }, 20000);
}
$("loadBtn").addEventListener("click", () => { const c = cred(); if (c) load(c); });
$("nick").addEventListener("keydown", e => { if (e.key === "Enter") { const c = cred(); if (c) load(c); } });
// 패치노트: 새 버전이 있으면 버튼에 점 표시, 열면 읽음 처리
const LSP = "dosa-notebook-site-pn";
let PN = null;
function pnRender(){
  const box = $("pnBody"); box.textContent = "";
  if (!PN || !PN.length) { box.textContent = "패치노트를 불러오지 못했어요."; return; }
  for (const v of PN) {
    const d = document.createElement("div"); d.className = "pn-ver";
    const h3 = document.createElement("h3"); h3.textContent = "v" + v.v;
    const sm = document.createElement("small"); sm.textContent = v.date || ""; h3.appendChild(sm);
    const ul = document.createElement("ul");
    for (const it of v.items || []) { const li = document.createElement("li"); li.textContent = it; ul.appendChild(li); }
    d.append(h3, ul); box.appendChild(d);
  }
}
fetch("patchnotes.json?t=" + Date.now()).then(r => r.json()).then(j => {
  PN = j;
  let seen = null; try { seen = localStorage.getItem(LSP); } catch (e) {}
  if (PN.length && seen !== PN[0].v) $("pnDot").hidden = false;
}).catch(() => {});
$("pnBtn").addEventListener("click", () => {
  pnRender(); $("pnDlg").showModal();
  if (PN && PN.length) { $("pnDot").hidden = true; try { localStorage.setItem(LSP, PN[0].v); } catch (e) {} }
});
$("pnClose").addEventListener("click", () => $("pnDlg").close());
$("pnDlg").addEventListener("click", e => { if (e.target === $("pnDlg")) $("pnDlg").close(); });
// 커뮤니티 소식: 클라우드 예약 작업이 4시간마다 community.json 을 갱신
const LSC = "dosa-notebook-site-cm";
let CM = null;
function cel(tag, cls, txt){ const x = document.createElement(tag); if (cls) x.className = cls; if (txt != null) x.textContent = txt; return x; }
function cmRender(){
  const box = $("cmBody"); box.textContent = "";
  const es = (CM && CM.entries) || [];
  if (!es.length) { box.textContent = "아직 정리된 소식이 없어요."; return; }
  for (const e of es) {
    const d = cel("div", "pn-ver");
    const h3 = cel("h3", null, e.at || ""); h3.appendChild(cel("small", null, (e.range ? e.range + " · " : "") + "디시 새 글 " + ((e.counts || {}).dc || 0) + "개" + (((e.counts || {}).forum) ? " · 공지 " + e.counts.forum + "개" : "")));
    d.appendChild(h3);
    if (e.headline) d.appendChild(cel("p", "cm-hl", e.headline));
    for (const s of e.sections || []) {
      const sec = cel("div", "cm-sec"); sec.appendChild(cel("h4", null, s.h));
      const ul = cel("ul"); for (const it of s.items || []) ul.appendChild(cel("li", null, it));
      sec.appendChild(ul); d.appendChild(sec);
    }
    box.appendChild(d);
  }
  box.appendChild(cel("p", "cm-note", "디시 도깨비의세계 갤러리와 공식 포럼 글을 자동으로 요약한 내용이에요. 커뮤니티 의견이라 사실과 다를 수 있어요."));
}
fetch("community.json?t=" + Date.now()).then(r => r.json()).then(j => {
  CM = j;
  let seen = null; try { seen = localStorage.getItem(LSC); } catch (e) {}
  if (CM.entries && CM.entries.length && seen !== CM.entries[0].at) $("cmDot").hidden = false;
}).catch(() => {});
$("cmBtn").addEventListener("click", () => {
  cmRender(); $("cmDlg").showModal();
  if (CM && CM.entries && CM.entries.length) { $("cmDot").hidden = true; try { localStorage.setItem(LSC, CM.entries[0].at); } catch (e) {} }
});
$("cmClose").addEventListener("click", () => $("cmDlg").close());
$("cmDlg").addEventListener("click", e => { if (e.target === $("cmDlg")) $("cmDlg").close(); });
''' + h[b:]

# 추천 트리: 내 분석 결과가 있으면 그걸, 없으면 예시
rep('const RECS = ', 'let RECS = ')
i = h.index('let RECS = ')
j = h.index('\n', i)
h = h[:j] + '\nconst EXAMPLE_RECS = RECS;' + h[j:]
rep('$("recBasis").textContent = "참고용 예시 · 계산 기준 캐릭터: " + RECS.basis + " · " + RECS.updated + " 계산. 강화 단계가 다르면 순위가 달라질 수 있습니다.";',
    '$("recBasis").textContent = myRes ? ("내 추천 · " + RECS.basis + " · " + RECS.updated + " 계산" + ((RECS.notes || []).length ? " · " + RECS.notes.join(" ") : ""))'
    ' : "아직 내 분석 결과가 없어요. 저장하면 2~3분 뒤 자동으로 계산돼요. 아래는 다른 캐릭터 기준 예시입니다(" + RECS.basis + ").";')

# 시작: 저장된 닉네임이 있으면 자동 불러오기, 없으면 임시 저장본
a = h.index('try {\n  const raw = localStorage.getItem(LS);')
b = h.index('\n', h.index('} catch (e) { setStatus("이 브라우저는 저장을 막고 있습니다', a))
h = h[:a] + r'''(function(){
  let c = null;
  try { c = JSON.parse(localStorage.getItem(LSA) || "null"); } catch (e) {}
  if (c && c.nick) { $("nick").value = c.nick; load({nick: c.nick, pin: PIN}); return; }
  try { const raw = localStorage.getItem(LS); if (raw) { state = tidy(normalize(JSON.parse(raw))); renderAll(); } } catch (e) {}
  setStatus("닉네임을 입력하고 불러오기를 누르세요. 처음이면 정보를 입력한 뒤 저장하면 등록돼요");
})();''' + h[b:]
h = h.replace("__API__", api)
assert "localStorage.setItem(LS, JSON.stringify(state)); dirty = false; setStatus(\"저장됨 · 이 브라우저에만\"" not in h
page = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<title>도사 수첩</title>\n<style>body{margin:0}</style>\n</head>\n<body>\n' + h.replace("<title>도사 수첩</title>", "", 1) + '\n</body>\n</html>\n')
open(out, "w", encoding="utf-8").write(page)
print("ok", len(page))
