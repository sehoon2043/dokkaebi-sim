// 추천 빌드 탭: 사냥터 → 광역/단일 → 생존·믹스·딜 카드(사이트 계산 1위 + 커뮤니티 빌드). [이걸로]는 바로 저장(추천 다시 계산 없음)
const TIER_ORDER = ["생존", "믹스", "딜"];
const TIER_SUB = {"생존": "회복·보호막 2개 이상", "믹스": "회복·보호막 1개", "딜": "회복·보호막 없이 딜"};
const HEAL_N = new Set(["생명의 흐름", "생명의 축복"]);
const LSGR = "dosa-notebook-site-ground";
let bdGround = null;
try { bdGround = localStorage.getItem(LSGR); } catch (e) {}
function iconRow(order, ult){
  const row = el("div", {class:"icrow"});
  order.forEach((n, i) => {
    const s = el("span", {class:"ic" + (n === ult ? " ult" : HEAL_N.has(n) ? " heal" : ""), title: (i + 1) + ". " + n + (n === ult ? " (궁극기)" : "")});
    s.appendChild(el("i", null, String(i + 1)));
    if (ICONS[n]) s.appendChild(el("img", {src: "icons/" + ICONS[n], alt: n, width: "32", height: "32", loading: "lazy"}));
    else s.appendChild(el("b", null, n.slice(0, 3)));
    row.appendChild(s);
  });
  return row;
}
function fmtPct(v){
  if (v == null) return "";
  if (Math.abs(v) < 0.5) return "비슷";
  return (v > 0 ? "+" : "") + v.toFixed(1) + "%";
}
// 내 빌드·광역/단일 즉시 저장: 수첩 data의 prefStyle·mybuilds만 서버로(다른 수정은 저장 버튼으로)
async function sendPick(){
  saveDraft();
  if (!auth) { setStatus("닉네임을 불러오면 내 빌드가 서버에 저장돼요(지금은 이 브라우저에만)", "warn"); return; }
  try {
    const r = await api(null, {a: "pick", nick: auth.nick, pin: auth.pin || PIN, prefStyle: state.prefStyle, mybuilds: state.mybuilds});
    if (r.ok) setStatus("내 빌드 저장됨 · 추천은 다시 계산하지 않아요", "ok");
    else setStatus(ERR[r.err] || "내 빌드 저장 실패", "warn");
  } catch (e) { setStatus("서버에 연결하지 못했어요. 잠시 뒤 다시 눌러 주세요", "warn"); }
}
function sameOrder(a, b){ return !!a && !!b && a.length === b.length && a.every((x, i) => x === b[i]); }
function pickBuild(g, st, t, from, src, commId){
  const prev = state.mybuilds[g] || {};
  const b = {tier: t, style: st, from, order: src.order.slice(), ult: src.ult, slots: (src.slots || []).slice(), pickedAt: Date.now()};
  if (from === "comm") b.commId = commId;
  if (prev.result) b.result = prev.result;
  state.mybuilds[g] = b;
  sendPick(); renderBuilds();
  if (typeof renderMyBuilds === "function") renderMyBuilds();
}
function pickBtn(g, st, t, from, src, commId){
  const mb = state.mybuilds[g];
  const mine = mb && mb.tier === t && mb.style === st && sameOrder(mb.order, src.order);
  const b = el("button", {type:"button", class:"bd-pick", "aria-pressed": mine ? "true" : "false"}, mine ? "내 빌드 ✓" : "이걸로");
  b.addEventListener("click", () => pickBuild(g, st, t, from, src, commId));
  return b;
}
function calcCand(g, st, t, c){
  const d = el("div", {class:"bd-cand"});
  d.appendChild(el("div", {class:"nm"}, "사이트 계산 1위 · " + c.label));
  const kind = {mob: "몰이 점수", field: "처치 속도", boss: "보스 점수"}[c.kind] || "딜";
  const parts = [];
  if (g === "boss") parts.push("보스 트리 1위");
  else if (t === "딜") parts.push(kind + " 기준(딜 카드)");
  else parts.push("딜 카드 대비 " + kind + " " + fmtPct(c.dmgPct));
  parts.push(c.sus > 0 ? "유지력: 초당 공격력의 " + c.sus.toFixed(1) + "%" : "회복·보호막 없음");
  d.appendChild(el("div", {class:"meta"}, parts.join(" · ")));
  d.appendChild(iconRow(c.order, c.ult));
  d.appendChild(pickBtn(g, st, t, "calc", c));
  return d;
}
function commCand(g, st, t, e, extra){
  const k = (RECS.decks || {})[String(e.id)];
  if (!k) return null;
  const d = el("div", {class:"bd-cand"});
  const nm = el("div", {class:"nm"}); nm.appendChild(el("span", {class:"bd-tag"}, "커뮤니티")); nm.appendChild(document.createTextNode(k.name + (extra || ""))); d.appendChild(nm);
  const meta = el("div", {class:"meta"}, "작성 " + k.author + " · 추천 " + k.likes + (e.pct != null ? " · 계산 1위 대비 " + fmtPct(e.pct) : ""));
  if (k.video) { meta.appendChild(document.createTextNode(" · ")); const a = el("a", {href: k.video, target: "_blank", rel: "noopener"}, "영상"); meta.appendChild(a); }
  d.appendChild(meta);
  if (k.missing && k.missing.length) d.appendChild(el("div", {class:"meta warn"}, "안 배운 도술 " + k.missing.length + "개: " + k.missing.join(", ")));
  d.appendChild(iconRow(k.order, k.ult));
  d.appendChild(pickBtn(g, st, t, "comm", k, e.id));
  return d;
}
function card(g, st, t, c){
  const mb = state.mybuilds[g];
  const box = el("div", {class:"bd-card" + (mb && mb.tier === t && mb.style === st ? " mine" : "")});
  const h = el("div", {class:"bd-head"}); h.appendChild(el("h3", null, t)); h.appendChild(el("small", null, TIER_SUB[t]));
  if (mb && mb.tier === t && mb.style === st) h.appendChild(el("span", {class:"bd-badge"}, "내 빌드"));
  box.appendChild(h);
  if (c.calc) box.appendChild(calcCand(g, st, t, c.calc));
  else box.appendChild(el("p", {class:"bd-note"}, g === "boss" && t !== "딜" ? "보스 생존·믹스 계산은 준비 중이에요. 아래 커뮤니티 빌드를 참고하세요." : "배운 도술로는 이 조건의 트리를 계산할 수 없어요."));
  const comm = (c.comm || []).filter(e => (RECS.decks || {})[String(e.id)]);
  if (comm.length) box.appendChild(commCand(g, st, t, comm[0]));
  else box.appendChild(el("p", {class:"bd-note"}, "이 조건의 커뮤니티 빌드가 아직 없어요."));
  if (comm.length > 1) {
    const more = el("details", {class:"bd-more"}); more.appendChild(el("summary", null, "커뮤니티 빌드 " + (comm.length - 1) + "개 더 ▾"));
    for (const e of comm.slice(1)) more.appendChild(commCand(g, st, t, e));
    box.appendChild(more);
  }
  return box;
}
function renderBuilds(){
  const G = RECS.grounds, box = $("bd"); box.textContent = "";
  const keys = Object.keys(G);
  if (!keys.includes(bdGround)) bdGround = keys.includes("well") ? "well" : keys[0];
  $("bdBasis").textContent = (myRes ? "내 추천 · " : "아직 내 분석 결과가 없어요. 아래는 예시 캐릭터 기준 · ") + RECS.basis + " · " + RECS.updated + " 계산"
    + ((RECS.notes || []).length ? " · " + RECS.notes.join(" ") : "");
  const chips = el("div", {class:"bd-chips", role:"tablist", "aria-label":"사냥터"});
  for (const k of keys) {
    const b = el("button", {type:"button", class:"tab", role:"tab", "aria-selected": k === bdGround ? "true" : "false"}, G[k].name);
    b.addEventListener("click", () => { bdGround = k; try { localStorage.setItem(LSGR, k); } catch (e) {} renderBuilds(); });
    chips.appendChild(b);
  }
  box.appendChild(chips);
  const g = G[bdGround], styles = Object.keys(g.styles);
  const st = styles.includes(state.prefStyle) ? state.prefStyle : styles[0];
  if (styles.length > 1) {
    const seg = el("div", {class:"bd-seg", role:"group", "aria-label":"광역/단일"});
    for (const s of styles) {
      const b = el("button", {type:"button", "aria-pressed": s === st ? "true" : "false"}, s);
      b.addEventListener("click", () => { if (state.prefStyle === s) return; state.prefStyle = s; sendPick(); renderBuilds(); });
      seg.appendChild(b);
    }
    box.appendChild(seg);
  }
  const cards = el("div", {class:"bd-cards"});
  for (const t of TIER_ORDER) cards.appendChild(card(bdGround, st, t, g.styles[st][t]));
  box.appendChild(cards);
  const un = (RECS.unassigned || []).filter(e => (RECS.decks || {})[String(e.id)]);
  if (un.length) {
    const det = el("details", {class:"bd-un"}); det.appendChild(el("summary", null, "사냥터 미지정 커뮤니티 빌드 " + un.length + "개 ▾"));
    // 여기서 [이걸로]를 누르면 지금 보고 있는 사냥터의 내 빌드로 저장
    for (const e of un) det.appendChild(commCand(bdGround, e.style, e.tier, e, " (" + e.style + " · " + e.tier + ")"));
    box.appendChild(det);
  }
}
// 내 수첩: 사냥터별 내 빌드 + 돌려 본 결과(물약·분당 엽전·분당 처치). 바꾸면 바로 저장(추천 다시 계산 없음)
let mbT = null;
function mbSave(){ clearTimeout(mbT); mbT = setTimeout(sendPick, 800); }
function renderMyBuilds(){
  const box = $("mb"); if (!box) return; box.textContent = "";
  const G = (RECS && RECS.grounds) || {}, gk = Object.keys(G);
  const keys = Object.keys(state.mybuilds || {}).filter(g => state.mybuilds[g] && state.mybuilds[g].order)
    .sort((a, b) => (gk.indexOf(a) + 1 || 99) - (gk.indexOf(b) + 1 || 99));
  if (!keys.length) { box.appendChild(el("p", {class:"bd-note"}, "추천 빌드 탭에서 [이걸로]를 누르면 사냥터별로 여기에 저장돼요.")); return; }
  const list = el("div", {class:"mb-list"});
  for (const g of keys) {
    const b = state.mybuilds[g], r = b.result || {};
    const it = el("div", {class:"mb-item"});
    let src = "사이트 계산 1위";
    if (b.from === "comm") { const k = (RECS.decks || {})[String(b.commId)]; src = "커뮤니티: " + (k ? k.name : "덱 #" + b.commId); }
    const h = el("h3", null, G[g] ? G[g].name : g); h.appendChild(el("small", null, b.style + " · " + b.tier + " · " + src)); it.appendChild(h);
    it.appendChild(iconRow(b.order, b.ult));
    const res = el("div", {class:"mb-res"}); res.appendChild(el("b", null, "돌려 본 결과"));
    const pl = el("label", null, "물약"), ps = el("select", {style:"width:auto"});
    for (const [v, t] of [["", "안 적음"], ["yes", "썼음"], ["no", "안 씀"]]) ps.appendChild(el("option", {value: v}, t));
    ps.value = r.potion === true ? "yes" : r.potion === false ? "no" : "";
    pl.appendChild(ps); res.appendChild(pl);
    const num = (lab, key) => {
      const l = el("label", null, lab), inp = el("input", {type:"number", inputmode:"decimal", min:"0", step:"any"});
      inp.value = r[key] ?? ""; l.appendChild(inp); res.appendChild(l); return inp;
    };
    const ci = num("분당 엽전", "coinPerMin"), ki = num("분당 처치", "killPerMin");
    const upd = () => {
      const nr = {at: Date.now()}, c = parseFloat(ci.value), k = parseFloat(ki.value);
      if (ps.value) nr.potion = ps.value === "yes";
      if (isFinite(c)) nr.coinPerMin = c;
      if (isFinite(k)) nr.killPerMin = k;
      if (Object.keys(nr).length > 1) b.result = nr; else delete b.result;
      mbSave();
    };
    ps.addEventListener("change", upd); ci.addEventListener("input", upd); ki.addEventListener("input", upd);
    it.appendChild(res); list.appendChild(it);
  }
  box.appendChild(list);
}
