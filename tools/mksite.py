# 공개 수첩(브라우저 저장판) → GitHub Pages 사이트(저장 서버 + 자동 분석 결과 표시)
#   python tools/mksite.py <공개 수첩 html> <출력 index.html> <저장 서버 URL>
import json, os, sys

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
    '\n    <button type="button" id="cmBtn" class="pn-btn">커뮤니티 소식<span class="pn-dot" id="cmDot" hidden></span></button>'
    '\n    <button type="button" id="gmBtn" class="pn-btn">길드원 현황</button>')
rep('  <div class="cols">',
    '  <dialog id="pnDlg" aria-labelledby="pnTitle"><div class="pn-head"><h2 id="pnTitle">패치노트</h2>'
    '<button type="button" id="pnClose" aria-label="닫기">닫기</button></div><div id="pnBody">불러오는 중…</div></dialog>\n'
    '  <dialog id="cmDlg" class="pn-dlg" aria-labelledby="cmTitle"><div class="pn-head"><h2 id="cmTitle">커뮤니티 소식</h2>'
    '<button type="button" id="cmClose" aria-label="닫기">닫기</button></div><div id="cmBody">불러오는 중…</div></dialog>\n'
    '  <div id="anaBox" class="ana" hidden role="status" aria-live="polite"><div class="ana-top"><b id="anaTitle">추천 트리 계산 중</b><span id="anaPct">0%</span></div>'
    '<div class="ana-bar"><i id="anaFill"></i></div><div class="ana-sub" id="anaSub"></div></div>\n'
    '  <dialog id="gmDlg" class="pn-dlg" aria-labelledby="gmTitle"><div class="pn-head"><h2 id="gmTitle">길드원 현황</h2>'
    '<button type="button" id="gmClose" aria-label="닫기">닫기</button></div><div id="gmBody">불러오는 중…</div></dialog>\n\n  <div class="cols">')
rep('.bar .status{',
    '.pn-btn{position:relative}.pn-dot{position:absolute;top:-3px;right:-3px;width:9px;height:9px;border-radius:50%;background:var(--warn)}\n'
    '#pnDlg,#cmDlg{width:min(600px,calc(100vw - 32px));max-height:80vh;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink);padding:0}\n'
    '#pnDlg::backdrop,#cmDlg::backdrop,#gmDlg::backdrop{background:rgba(0,0,0,.45)}\n#cmBody,#gmBody{padding:4px 16px 16px}\n'
    '#gmDlg{width:min(860px,calc(100vw - 32px));max-height:85vh;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--ink);padding:0}\n'
    '.gm-wrap{overflow-x:auto;margin-top:6px}.gm-tbl{border-collapse:collapse;font-size:.85rem;white-space:nowrap;width:100%}\n'
    '.gm-tbl th,.gm-tbl td{padding:5px 7px;border-bottom:1px solid var(--line);text-align:center}.gm-tbl th{font-size:.76rem;color:var(--muted);font-weight:600}\n'
    '.gm-tbl td.nk,.gm-tbl th.nk{text-align:left;position:sticky;left:0;background:var(--panel)}.gm-tbl td.nk{font-weight:600}\n'
    '.gm-tbl td.z{color:var(--muted)}.gm-tbl td.top{font-weight:700;color:var(--accent)}.gm-tbl td.main{font-size:.78rem;color:var(--muted)}\n'
    '.gm-tbl tr.me td{background:var(--accent-soft)}.gm-tbl tfoot td{color:var(--muted);font-size:.8rem;border-bottom:0}\n'
    '.ana{margin:0 0 12px;padding:10px 14px;border:1px solid var(--accent);border-radius:10px;background:var(--accent-soft)}.ana.warn{border-color:var(--warn)}\n'
    '.ana-top{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.ana-top b{font-size:.95rem}.ana-top span{font-weight:700;color:var(--accent);font-variant-numeric:tabular-nums}\n'
    '.ana-bar{height:8px;margin:7px 0 5px;border-radius:5px;background:var(--line);overflow:hidden}.ana-bar i{display:block;height:100%;width:2%;background:var(--accent);border-radius:5px;transition:width .6s ease}\n'
    '.ana.warn .ana-bar i{background:var(--warn)}.ana-sub{font-size:.84rem;color:var(--ink);opacity:.85}\n'
    '.rec-legend{font-size:.78rem;color:var(--muted);margin:2px 0 0}.rec-verify summary{cursor:pointer;font-size:.82rem;color:var(--muted)}\n'
    '.cm-hl{margin:0 0 8px;font-weight:600}.cm-sec{margin-top:8px}.cm-sec h4{margin:0 0 4px;font-size:.9rem;color:var(--accent)}\n'
    '.cm-top{margin:12px 0 4px;padding:10px 12px;border-radius:8px;background:var(--accent-soft);font-weight:600;line-height:1.45}\n'
    '.cm-meta{font-size:.8rem;color:var(--muted);margin:6px 0 2px}\n'
    '.cm-list{list-style:none;margin:0;padding:0;display:grid;gap:5px;font-size:.9rem;line-height:1.45}\n'
    '.cm-list li{display:flex;gap:6px;align-items:baseline}\n'
    '.cm-k{flex:none;font-size:.7rem;font-weight:600;padding:1px 6px;border-radius:9px;border:1px solid currentColor;color:var(--muted)}\n'
    '.cm-k.k-official{color:var(--accent)}.cm-k.k-report{color:var(--ok)}.cm-k.k-warn{color:var(--warn)}\n'
    '.cm-hist{margin-top:14px;border-top:1px solid var(--line);padding-top:8px}.cm-hist summary{cursor:pointer;font-size:.88rem;color:var(--muted)}\n'
    '.cm-hist .pn-ver{font-size:.88rem}\n'
    '.cm-note{font-size:.8rem;color:var(--muted);margin-top:10px}\n'
    '.pn-head{position:sticky;top:0;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px 16px;background:var(--panel);border-bottom:1px solid var(--line)}\n'
    '.pn-head h2{margin:0;font-size:1.1rem}\n#pnBody{padding:4px 16px 16px}\n'
    '.pn-ver{padding-block:12px;border-bottom:1px solid var(--line)}.pn-ver:last-child{border-bottom:0}\n'
    '.pn-ver h3{margin:0 0 6px;font-size:.98rem}.pn-ver h3 small{color:var(--muted);font-weight:400;margin-left:6px}\n'
    '.pn-ver ul{margin:0;padding-left:18px;display:grid;gap:3px;font-size:.9rem}\n'
    '.bar .status{')

# 프리셋은 쓰지 않음: 오른쪽은 추천 트리만. 도술 칸 수는 강화 레벨 위로 옮김(추천 트리 계산에 쓰임)
rep('<div class="ptabs" role="tablist" aria-label="오른쪽 패널"><button type="button" role="tab" data-rt="presets">내 프리셋</button><button type="button" role="tab" data-rt="recs">추천 트리</button></div>', '')
rep('let rightTab = "presets", recActive', 'let rightTab = "recs", recActive')
rep('<label class="toggle">열린 칸<select id="slotCount" style="width:auto"><option>5</option><option>6</option><option>7</option><option>8</option></select></label>', '')
rep('    <div class="lvrow" id="lvrow" role="group" aria-label="스타일별 강화 레벨"></div>',
    '    <div class="slotrow"><label class="toggle">도술 칸 수<select id="slotCount" style="width:auto"><option>5</option><option>6</option><option>7</option><option>8</option></select></label>'
    '<span class="hint">게임에서 열린 도술 칸 수예요. 추천 트리를 이 칸 수에 맞춰 계산해요.</span></div>\n'
    '    <div class="lvrow" id="lvrow" role="group" aria-label="스타일별 강화 레벨"></div>')
rep('s.slotCount = s.slotCount || 7;', 's.slotCount = s.slotCount || 8;')

rep('.rec-copy{', '.slotrow{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin-bottom:10px}.slotrow .hint{margin:0}\n.rec-copy{display:none!important}\n.rec-copy{')

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
h = h[:a] + r'''const LS = "dosa-notebook-site-v1", LSA = "dosa-notebook-site-auth", LSR = "dosa-notebook-site-res";
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
  setStatus("서버에서 최신 정보를 불러오는 중… (화면은 마지막으로 받은 내용)");
  try {
    const r = await api({a: "load", nick: c.nick, pin: c.pin});
    if (!r.ok && r.err === "none") { remember(c); setStatus("새 닉네임이에요. 정보를 입력하고 저장을 누르면 등록돼요", "ok"); return; }
    if (!r.ok) { setStatus(ERR[r.err] || "불러오기 실패", "warn"); return; }
    remember(c);
    state = tidy(normalize(r.data || {})); dirty = false; renderAll();
    applyResult(r.result);
    // 서버 응답이 느릴 때가 있어 마지막으로 받은 내용을 이 브라우저에 보관(다음에 열면 먼저 보여 줌)
    saveDraft(); try { localStorage.setItem(LSR, JSON.stringify({nick: c.nick, res: r.result || null})); } catch (e) {}
    const pending = !r.result || String(r.resultFor) !== String(r.updatedAt);
    setStatus(c.nick + " 불러옴" + (pending ? " · 추천 트리 계산 중" : " · 추천 트리가 최신이에요"), "ok");
    if (pending) watch(c, r.updatedAt, Number(r.updatedAt) || Date.now()); else anaHide();
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
      setStatus((r.created ? "등록 완료" : "저장됨") + " · 추천 트리 계산을 시작해요", "ok");
      watch(c, r.updatedAt, Date.now());
    }
  } catch (e) { setStatus("서버에 연결하지 못했어요. 잠시 뒤 다시 저장하세요", "warn"); }
  saving = false;
}
// 추천 트리 계산 진행률: 저장 뒤 4초마다 서버 상태(status)를 받아 막대·단계·남은 시간을 보여 준다
let watchT = null, watchSeq = 0;
function anaHide(){ clearTimeout(watchT); watchSeq++; $("anaBox").hidden = true; }
function fmtLeft(ms){
  const s = Math.max(10, Math.round(ms / 10000) * 10);
  return s >= 60 ? "약 " + Math.floor(s / 60) + "분" + (s % 60 ? " " + (s % 60) + "초" : "") + " 남음" : "약 " + s + "초 남음";
}
function anaShow(pct, title, sub, warn){
  $("anaBox").hidden = false; $("anaBox").classList.toggle("warn", !!warn);
  $("anaTitle").textContent = title; $("anaPct").textContent = Math.round(pct) + "%";
  $("anaFill").style.width = Math.max(2, Math.min(100, pct)) + "%"; $("anaSub").textContent = sub;
}
function watch(c, upd, t0){
  clearTimeout(watchT); const seq = ++watchSeq;
  anaShow(0, "추천 트리 계산 준비 중", "계산 서버를 깨우는 중이에요(보통 30초~1분)");
  const tick = async () => {
    if (seq !== watchSeq) return;
    let r = null;
    try { r = await api({a: "status", nick: c.nick}); } catch (e) {}
    if (seq !== watchSeq) return;
    if (r && r.ok && String(r.resultFor) === String(upd)) {
      anaShow(100, "추천 트리 계산 완료", "결과를 불러오는 중…");
      try {
        const x = await api({a: "load", nick: c.nick, pin: c.pin});
        if (x.ok) { applyResult(x.result); try { localStorage.setItem(LSR, JSON.stringify({nick: c.nick, res: x.result || null})); } catch (e) {} }
      } catch (e) {}
      rightTab = "recs"; renderRight(); setStatus("추천 트리가 갱신됐어요", "ok");
      watchT = setTimeout(anaHide, 2500); return;
    }
    if (r && r.ok && String(r.updatedAt) !== String(upd)) { watch(c, r.updatedAt, Number(r.updatedAt) || Date.now()); return; }
    const now = (r && r.now) || Date.now(), g = r && r.progress;
    const waited = now - t0;
    if (g && String(g.for) === String(upd) && g.pct > 0) {
      const left = g.start ? (now - g.start) / g.pct * (100 - g.pct) : 0;
      anaShow(g.pct, "추천 트리 계산 중 · " + g.stage, left ? fmtLeft(left) : "남은 시간 계산 중…");
    } else if (g && String(g.for) === String(upd)) {
      anaShow(0, "추천 트리 계산 대기 중", g.stage + " · 다른 길드원 계산이 끝나면 바로 시작해요");
    } else if (waited > 20 * 60 * 1000) {
      anaShow(0, "계산이 늦어지고 있어요", "잠시 뒤 '불러오기'를 눌러 보세요. 계속 안 되면 관리자에게 알려 주세요", true);
      return;
    } else {
      anaShow(0, "추천 트리 계산 준비 중", "계산 서버를 깨우는 중이에요(보통 30초~1분) · " + Math.round(waited / 1000) + "초 지남");
    }
    watchT = setTimeout(tick, 4000);
  };
  watchT = setTimeout(tick, 2000);
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
const CMK = {"공식": "k-official", "제보": "k-report", "의견": "", "주의": "k-warn"};
function cmItem(it){
  const li = cel("li");
  const t = typeof it === "string" ? {t: it} : it;
  if (t.k) li.appendChild(cel("span", "cm-k " + (CMK[t.k] || ""), t.k));
  li.appendChild(cel("span", null, t.t));
  return li;
}
function cmSections(d, secs){
  for (const s of secs || []) {
    const sec = cel("div", "cm-sec"); sec.appendChild(cel("h4", null, s.h));
    const ul = cel("ul", "cm-list"); for (const it of s.items || []) ul.appendChild(cmItem(it));
    sec.appendChild(ul); d.appendChild(sec);
  }
}
function cmRender(){
  const box = $("cmBody"); box.textContent = "";
  const sm = CM && CM.summary, es = (CM && CM.entries) || [];
  if (!sm && !es.length) { box.textContent = "아직 정리된 소식이 없어요."; return; }
  if (sm) {
    const c = sm.counts || {};
    box.appendChild(cel("p", "cm-meta", (sm.range || "") + " 합산 · 디시 글 " + (c.dc || 0).toLocaleString() + "개" + (c.forum ? " · 공지 " + c.forum + "개" : "") + " · " + (sm.at || "") + " 갱신"));
    if (sm.headline) box.appendChild(cel("p", "cm-top", sm.headline));
    cmSections(box, sm.sections);
  }
  if (es.length) {
    const det = cel("details", "cm-hist"); det.appendChild(cel("summary", null, "구간별 기록 " + es.length + "개 보기"));
    for (const e of es) {
      const d = cel("div", "pn-ver");
      const h3 = cel("h3", null, e.at || ""); h3.appendChild(cel("small", null, (e.range ? e.range + " · " : "") + "디시 새 글 " + ((e.counts || {}).dc || 0) + "개"));
      d.appendChild(h3);
      if (e.headline) d.appendChild(cel("p", "cm-hl", e.headline));
      cmSections(d, e.sections);
      det.appendChild(d);
    }
    box.appendChild(det);
  }
  box.appendChild(cel("p", "cm-note", "디시 도깨비의세계 갤러리와 공식 포럼 글을 자동으로 요약한 내용이에요. '공식' 표시 외에는 커뮤니티 의견이라 사실과 다를 수 있어요."));
}
const cmStamp = () => (CM && CM.summary && CM.summary.at) || (CM && CM.entries && CM.entries.length && CM.entries[0].at) || null;
fetch("community.json?t=" + Date.now()).then(r => r.json()).then(j => {
  CM = j;
  let seen = null; try { seen = localStorage.getItem(LSC); } catch (e) {}
  if (cmStamp() && seen !== cmStamp()) $("cmDot").hidden = false;
}).catch(() => {});
$("cmBtn").addEventListener("click", () => {
  cmRender(); $("cmDlg").showModal();
  if (cmStamp()) { $("cmDot").hidden = true; try { localStorage.setItem(LSC, cmStamp()); } catch (e) {} }
});
$("cmClose").addEventListener("click", () => $("cmDlg").close());
$("cmDlg").addEventListener("click", e => { if (e.target === $("cmDlg")) $("cmDlg").close(); });
// 길드원 현황: 저장된 길드원의 도술 강화 레벨 모아 보기(서버 members는 닉네임·강화·도술 수·각성만 줌)
const GM_ST = ["절명", "연타", "강타", "척살", "저격", "주술", "파멸", "강인", "기동", "헌신", "기만", "제압"];
// 서버 응답이 느려서 페이지를 열 때 미리 받아 두고, 마지막으로 받은 목록은 이 브라우저에 보관해 창을 바로 띄운다
const LSG = "dosa-notebook-site-gm";
let GM = null, gmBusy = null;
try { GM = JSON.parse(localStorage.getItem(LSG) || "null"); } catch (e) {}
function gmFetch(){
  if (gmBusy) return gmBusy;
  gmBusy = api({a: "members"}).then(r => {
    if (r && r.ok && r.list) { GM = {list: r.list, at: Date.now()}; try { localStorage.setItem(LSG, JSON.stringify(GM)); } catch (e) {} }
  }).catch(() => {}).finally(() => { gmBusy = null; if ($("gmDlg").open) gmRender(); });
  return gmBusy;
}
function gmRender(){
  const box = $("gmBody"); box.textContent = "";
  if (!GM) { box.textContent = gmBusy ? "불러오는 중…" : "길드원 정보를 불러오지 못했어요. 잠시 뒤 다시 열어 보세요."; return; }
  const r = GM;
  const lv = (m, s) => Number((m.levels || {})[s]) || 0;
  const sum = m => GM_ST.reduce((a, s) => a + lv(m, s), 0);
  const L = r.list.filter(m => sum(m) > 0).sort((a, b) => sum(b) - sum(a));
  if (!L.length) { box.textContent = "아직 강화 레벨을 저장한 길드원이 없어요."; return; }
  const cols = GM_ST.filter(s => L.some(m => lv(m, s) > 0));
  const mx = {}; for (const s of cols) mx[s] = Math.max(...L.map(m => lv(m, s)));
  box.appendChild(cel("p", "cm-meta", "길드원 " + L.length + "명 · 강화 레벨 합계 순 · 열마다 가장 높은 레벨은 색으로 표시 · 각성 칸에 마우스를 올리면 도술 목록" + (gmBusy ? " · 최신 정보 확인 중…" : "")));
  const wrap = cel("div", "gm-wrap"), tb = cel("table", "gm-tbl");
  const hr = cel("tr"); hr.appendChild(cel("th", "nk", "닉네임")); hr.appendChild(cel("th", null, "주력"));
  for (const s of cols) hr.appendChild(cel("th", null, s));
  for (const x of ["합계", "각성", "저장"]) hr.appendChild(cel("th", null, x));
  const th = cel("thead"); th.appendChild(hr); tb.appendChild(th);
  const bd = cel("tbody");
  for (const m of L) {
    const tr = cel("tr", auth && auth.nick === m.nick ? "me" : null);
    tr.appendChild(cel("td", "nk", m.nick));
    const top = cols.filter(s => lv(m, s) > 0).sort((a, b) => lv(m, b) - lv(m, a)).slice(0, 2);
    tr.appendChild(cel("td", "main", top.join("·")));
    for (const s of cols) { const v = lv(m, s); tr.appendChild(cel("td", v === 0 ? "z" : v === mx[s] ? "top" : null, v ? String(v) : "·")); }
    tr.appendChild(cel("td", null, String(sum(m))));
    const aw = Object.entries(m.awaken || {});
    const ac = cel("td", aw.length ? null : "z", aw.length ? String(aw.length) : "·");
    if (aw.length) ac.title = aw.map(([n, k]) => n + " " + k + "단계").join("\n");
    tr.appendChild(ac);
    const dt = new Date(Number(m.updatedAt));
    tr.appendChild(cel("td", "z", isNaN(dt) ? "" : (dt.getMonth() + 1) + "/" + dt.getDate()));
    bd.appendChild(tr);
  }
  tb.appendChild(bd);
  const fr = cel("tr"); fr.appendChild(cel("td", "nk", "평균")); fr.appendChild(cel("td"));
  for (const s of cols) fr.appendChild(cel("td", null, (L.reduce((a, m) => a + lv(m, s), 0) / L.length).toFixed(1)));
  fr.appendChild(cel("td", null, (L.reduce((a, m) => a + sum(m), 0) / L.length).toFixed(0)));
  for (let i = 0; i < 2; i++) fr.appendChild(cel("td"));
  const tf = cel("tfoot"); tf.appendChild(fr); tb.appendChild(tf);
  wrap.appendChild(tb); box.appendChild(wrap);
  box.appendChild(cel("p", "cm-note", "수첩에 저장한 강화 레벨 기준이에요. 강화를 올렸으면 수첩에서 고치고 저장해 주세요."));
}
$("gmBtn").addEventListener("click", () => { gmFetch(); $("gmDlg").showModal(); gmRender(); });
setTimeout(gmFetch, 1500);
$("gmClose").addEventListener("click", () => $("gmDlg").close());
$("gmDlg").addEventListener("click", e => { if (e.target === $("gmDlg")) $("gmDlg").close(); });
''' + h[b:]

# 추천 트리: 내 분석 결과가 있으면 그걸, 없으면 예시
rep('const RECS = ', 'let RECS = ')
rep('"aria-selected": i === recActive ? "true" : "false"}, t.tab);',
    '"aria-selected": i === recActive ? "true" : "false"}, (t.best ? "★ " : "") + t.tab);')
rep('    rows[g].appendChild(b);\n  });\n',
    '    rows[g].appendChild(b);\n  });\n  if (RECS.trees.some(x => x.best)) tabs.appendChild(el("p", {class:"rec-legend"}, "★ 분류마다 가장 추천하는 트리"));\n')
rep('head.appendChild(el("b", null, t.tab + " · " + t.sub)); box.appendChild(head);',
    'head.appendChild(el("b", null, t.tab + " · " + t.sub)); if (t.best) head.appendChild(el("span", {class:"vbadge good"}, "추천")); box.appendChild(head);')
rep('    const ul3 = el("ul", {class:"rec-points alt"}); for (const s of v.lines) ul3.appendChild(el("li", null, s)); right.appendChild(ul3);',
    '    const dv = el("details", {class:"rec-verify"}); dv.appendChild(el("summary", null, "검증 내용 보기"));\n'
    '    const ul3 = el("ul", {class:"rec-points alt"}); for (const s of v.lines) ul3.appendChild(el("li", null, s)); dv.appendChild(ul3); right.appendChild(dv);')
i = h.index('let RECS = ')
j = h.index('\n', i)
# 예시 추천 트리: tools/example_recs.json(실제 분석 결과 한 건)이 있으면 그것으로 바꿈(새 형식 포인트·추천 표시)
EX_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "example_recs.json")
if os.path.exists(EX_PATH):
    h = h[:i] + 'let RECS = ' + json.dumps(json.load(open(EX_PATH, encoding="utf-8")), ensure_ascii=False) + ';' + h[j:]
    j = h.index('\n', i)
h = h[:j] + '\nconst EXAMPLE_RECS = RECS;' + h[j:]
rep('$("recBasis").textContent = "참고용 예시 · 계산 기준 캐릭터: " + RECS.basis + " · " + RECS.updated + " 계산. 강화 단계가 다르면 순위가 달라질 수 있습니다.";',
    '$("recBasis").textContent = myRes ? ("내 추천 · " + RECS.basis + " · " + RECS.updated + " 계산" + ((RECS.notes || []).length ? " · " + RECS.notes.join(" ") : ""))'
    ' : "아직 내 분석 결과가 없어요. 저장하면 자동으로 계산돼요(위쪽 진행 막대). 아래는 다른 캐릭터 기준 예시예요(" + RECS.basis + ").";')

# 시작: 저장된 닉네임이 있으면 자동 불러오기, 없으면 임시 저장본
a = h.index('try {\n  const raw = localStorage.getItem(LS);')
b = h.index('\n', h.index('} catch (e) { setStatus("이 브라우저는 저장을 막고 있습니다', a))
h = h[:a] + r'''(function(){
  let c = null;
  try { c = JSON.parse(localStorage.getItem(LSA) || "null"); } catch (e) {}
  if (c && c.nick) {
    $("nick").value = c.nick;
    try {
      const raw = localStorage.getItem(LS); if (raw) { state = tidy(normalize(JSON.parse(raw))); renderAll(); }
      const cr = JSON.parse(localStorage.getItem(LSR) || "null"); if (cr && cr.nick === c.nick && cr.res) applyResult(cr.res);
    } catch (e) {}
    load({nick: c.nick, pin: PIN}); return;
  }
  try { const raw = localStorage.getItem(LS); if (raw) { state = tidy(normalize(JSON.parse(raw))); renderAll(); } } catch (e) {}
  setStatus("닉네임을 입력하고 불러오기를 누르세요. 처음이면 정보를 입력한 뒤 저장하면 등록돼요");
})();''' + h[b:]
# 가독성: 강화 레벨 칸이 좁아 스타일 이름이 세로로 꺾이고 두 자리 숫자가 잘리던 것, 좁은 화면에서는 추천 트리를 도술 입력보다 먼저
rep('.rec-copy{display:none!important}', '.rec-copy{display:none!important}\n'
    '.lvrow{grid-template-columns:repeat(auto-fill,minmax(112px,1fr))!important}.lvrow label{white-space:nowrap}.lvrow input{width:3.6em;text-align:right}\n'
    '@media (max-width:1279.98px){#sec-recs{order:0}}')
# 좁은 화면(휴대폰): 추천 트리 / 도술 입력을 탭 버튼으로 나눠 한쪽만 보여 줌. PC(1280px 이상)는 두 패널 그대로
rep('  <div class="cols">',
    '  <div class="mtabs" role="tablist" aria-label="화면 전환"><button type="button" role="tab" data-mt="recs">추천 트리</button>'
    '<button type="button" role="tab" data-mt="skills">도술 입력</button></div>\n  <div class="cols">')
rep('.rec-legend{', '.mtabs{display:none}\n'
    '@media (max-width:1279.98px){.mtabs{display:flex;gap:6px;margin:0 0 4px}.mtabs button{flex:1;font-weight:600;padding:9px 12px}'
    '.mtabs button[aria-selected="true"]{background:var(--accent);border-color:var(--accent);color:var(--bg)}'
    'body[data-mt="recs"] #sec-skills{display:none}body[data-mt="skills"] #sec-recs{display:none}}\n.rec-legend{')
rep('$("gmBtn").addEventListener(', r"""// 휴대폰 탭: 마지막으로 본 탭을 기억(기본 추천 트리)
const LSM = "dosa-notebook-site-mt";
function setMt(t){
  document.body.dataset.mt = t;
  for (const b of document.querySelectorAll(".mtabs button")) b.setAttribute("aria-selected", b.dataset.mt === t ? "true" : "false");
  try { localStorage.setItem(LSM, t); } catch (e) {}
}
for (const b of document.querySelectorAll(".mtabs button")) b.addEventListener("click", () => { setMt(b.dataset.mt); window.scrollTo({top: 0}); });
(function(){ let t = null; try { t = localStorage.getItem(LSM); } catch (e) {} setMt(t === "skills" ? "skills" : "recs"); })();
$("gmBtn").addEventListener(""")
rep('      rightTab = "recs"; renderRight(); setStatus("추천 트리가 갱신됐어요", "ok");',
    '      rightTab = "recs"; renderRight(); setMt("recs"); setStatus("추천 트리가 갱신됐어요", "ok");')
h = h.replace("__API__", api)
assert "localStorage.setItem(LS, JSON.stringify(state)); dirty = false; setStatus(\"저장됨 · 이 브라우저에만\"" not in h
page = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<title>도사 수첩</title>\n<style>body{margin:0}</style>\n</head>\n<body>\n' + h.replace("<title>도사 수첩</title>", "", 1) + '\n</body>\n</html>\n')
open(out, "w", encoding="utf-8").write(page)
print("ok", len(page))
