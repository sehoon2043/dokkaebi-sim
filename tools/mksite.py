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
    '<h1>도사 수첩</h1>\n    <span class="auth"><input id="nick" placeholder="닉네임" maxlength="16" autocomplete="username">'
    '<input id="pin" placeholder="비밀번호 4자리" maxlength="4" inputmode="numeric" type="password" autocomplete="current-password">'
    '<button type="button" id="loadBtn">불러오기</button><button type="button" id="newBtn">처음 등록</button></span>')
rep('.bar .status{', '.auth{display:flex;flex-wrap:wrap;gap:6px;align-items:center}.auth input{width:120px}\n.bar .status{')

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
const ERR = {none: "등록된 닉네임이 없어요. 처음이면 '처음 등록'을 누르세요", pin: "비밀번호가 달라요", locked: "비밀번호를 여러 번 틀려 10분간 잠겼어요",
  input: "닉네임과 숫자 4자리 비밀번호를 입력하세요", size: "내용이 너무 길어요(메모·기록을 줄여 주세요)"};
function cred(){
  const nick = $("nick").value.trim(), pin = $("pin").value.trim();
  if (!nick || !/^\d{4}$/.test(pin)) { setStatus(ERR.input, "warn"); return null; }
  return {nick, pin};
}
function applyResult(res, upd){
  myRes = res && res.trees && res.trees.length ? res : null;
  RECS = myRes || EXAMPLE_RECS; recActive = 0; recConfirm = null;
  renderRight();
}
async function load(c){
  setStatus("불러오는 중…");
  try {
    const r = await api({a: "load", nick: c.nick, pin: c.pin});
    if (!r.ok) { setStatus(ERR[r.err] || "불러오기 실패", "warn"); return; }
    auth = c; try { localStorage.setItem(LSA, JSON.stringify(c)); } catch (e) {}
    state = tidy(normalize(r.data || {})); dirty = false; renderAll();
    applyResult(r.result);
    const pending = !r.result || String(r.resultFor) !== String(r.updatedAt);
    setStatus(c.nick + " 불러옴" + (pending ? " · 마지막 저장 내용은 다음 자동 분석 때 반영돼요" : " · 추천 트리가 최신이에요"), "ok");
  } catch (e) { setStatus("서버에 연결하지 못했어요. 잠시 뒤 다시 시도하세요", "warn"); }
}
async function save(create){
  if (saving) return;
  const c = auth || (create ? cred() : null);
  if (!c) { setStatus("닉네임·비밀번호로 '불러오기' 또는 '처음 등록'을 먼저 하세요", "warn"); return; }
  saving = true; setStatus("저장 중…");
  try {
    const r = await api(null, {a: "save", nick: c.nick, pin: c.pin, data: JSON.parse(JSON.stringify(state)), create: !!create});
    if (!r.ok) {
      setStatus(create && r.err === "pin" ? "이미 있는 닉네임이에요. 다른 닉네임을 쓰거나 '불러오기'를 누르세요" : (ERR[r.err] || "저장 실패"), "warn");
    } else {
      auth = c; try { localStorage.setItem(LSA, JSON.stringify(c)); } catch (e) {}
      dirty = false; saveDraft();
      setStatus((r.created ? "등록 완료" : "저장됨") + " · 매일 오전 9시·밤 9시 자동 분석에 반영돼요", "ok");
    }
  } catch (e) { setStatus("서버에 연결하지 못했어요. 잠시 뒤 다시 저장하세요", "warn"); }
  saving = false;
}
$("loadBtn").addEventListener("click", () => { const c = cred(); if (c) load(c); });
$("newBtn").addEventListener("click", () => { auth = null; save(true); });
''' + h[b:]
rep('$("saveBtn").addEventListener("click", () => { clearTimeout(timer); save(); });',
    '$("saveBtn").addEventListener("click", () => { clearTimeout(timer); save(false); });')

# 추천 트리: 내 분석 결과가 있으면 그걸, 없으면 예시
rep('const RECS = ', 'let RECS = ')
i = h.index('let RECS = ')
j = h.index('\n', i)
h = h[:j] + '\nconst EXAMPLE_RECS = RECS;' + h[j:]
rep('$("recBasis").textContent = "참고용 예시 · 계산 기준 캐릭터: " + RECS.basis + " · " + RECS.updated + " 계산. 강화 단계가 다르면 순위가 달라질 수 있습니다.";',
    '$("recBasis").textContent = myRes ? ("내 추천 · " + RECS.basis + " · " + RECS.updated + " 계산" + ((RECS.notes || []).length ? " · " + RECS.notes.join(" ") : ""))'
    ' : "아직 내 분석 결과가 없어요. 저장해 두면 매일 오전 9시·밤 9시에 자동으로 계산돼요. 아래는 다른 캐릭터 기준 예시입니다(" + RECS.basis + ").";')

# 시작: 저장된 닉네임이 있으면 자동 불러오기, 없으면 임시 저장본
a = h.index('try {\n  const raw = localStorage.getItem(LS);')
b = h.index('\n', h.index('} catch (e) { setStatus("이 브라우저는 저장을 막고 있습니다', a))
h = h[:a] + r'''(function(){
  let c = null;
  try { c = JSON.parse(localStorage.getItem(LSA) || "null"); } catch (e) {}
  if (c && c.nick) { $("nick").value = c.nick; $("pin").value = c.pin || ""; load(c); return; }
  try { const raw = localStorage.getItem(LS); if (raw) { state = tidy(normalize(JSON.parse(raw))); renderAll(); } } catch (e) {}
  setStatus("처음이면 닉네임과 비밀번호 4자리를 정하고 '처음 등록'을 누르세요");
})();''' + h[b:]
h = h.replace("__API__", api)
assert "localStorage.setItem(LS, JSON.stringify(state)); dirty = false; setStatus(\"저장됨 · 이 브라우저에만\"" not in h
page = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
        '<title>도사 수첩</title>\n<style>body{margin:0}</style>\n</head>\n<body>\n' + h.replace("<title>도사 수첩</title>", "", 1) + '\n</body>\n</html>\n')
open(out, "w", encoding="utf-8").write(page)
print("ok", len(page))
