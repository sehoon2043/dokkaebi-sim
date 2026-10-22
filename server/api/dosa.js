// 도사 수첩 저장 서버 (Vercel Functions + Upstash Redis). 예전 Apps Script(Code.gs)와 같은 요청·응답 형식
//   GET  ?a=load&nick=&pin=        내 수첩 + 분석 결과
//   GET  ?a=members                길드원 현황(닉네임·강화 레벨·각성만)
//   GET  ?a=status&nick=           추천 트리 계산 상태(저장 시각·결과 시각·진행률)
//   POST {a:"progress", key, nick, updatedAt, pct, stage}  분석 진행률 보고(관리자)
//   GET  ?a=data&name=&key=  /  POST {a:"setdata", key, name, value}   계산용 비공개 게임 데이터(관리자)
//   GET  ?a=pending|all&key=       분석할 프로필(관리자)
//   POST {a:"save", nick, pin, data, create}
//   POST {a:"pick", nick, pin, g?, build?, prefStyle?}   내 빌드·광역/단일 즉시 저장(재계산 없음, b:<닉네임> 해시. lib/pick.js)
//   POST {a:"result", key, nick, updatedAt, result}   분석 결과 기록(관리자)
//   POST {a:"import", key, profiles:[...]}            옮겨 오기(관리자)
// 환경 변수: ADMIN_KEY, GH_TOKEN(저장 직후 GitHub Actions 분석 요청), Upstash 연결 값(KV_REST_API_URL·KV_REST_API_TOKEN 또는 UPSTASH_REDIS_REST_URL·TOKEN)
// Redis 키: p:<닉네임> 프로필 전체, m:<닉네임> 길드원 현황 요약, g:<닉네임> 분석 진행률(1시간 뒤 삭제), nicks 닉네임 목록, lastDispatch:<해시>(1시간 뒤 삭제)
//           b:<닉네임> 내 빌드 해시(사냥터 키 → 빌드 JSON, _style → 광역/단일). load·all은 이것을 data에 합쳐 돌려준다
import { Redis } from "@upstash/redis";
import { createHash } from "node:crypto";
import { pickOps, mergePicks, forAll, MAX_FIELDS } from "../lib/pick.js";

const MAX_DATA = 45000;
const MEMBERS_HIDE = ["테스트"];
const GH_REPO = "sehoon2043/dokkaebi-sim";
const GH_WORKFLOW = "analyze.yml";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

let redis = null;
function db() {
  if (!redis) {
    redis = new Redis({
      url: process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL,
      token: process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN,
    });
  }
  return redis;
}

function out(obj) {
  return new Response(JSON.stringify(obj), { headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" } });
}

function cleanNick(s) {
  return String(s || "").trim().slice(0, 16);
}

function hash(nick, pin) {
  return createHash("sha256").update("dosa|" + nick + "|" + pin, "utf8").digest("hex");
}

function isAdmin(key) {
  return Boolean(process.env.ADMIN_KEY) && key === process.env.ADMIN_KEY;
}

function summary(p) {
  const d = p.data || {};
  const owned = d.owned || {};
  const awaken = {};
  for (const k of Object.keys(owned)) {
    const s = Number((owned[k] || {}).br || 0);
    if (s > 0) {
      awaken[k] = s;
    }
  }
  const res = p.result || {};
  const err = (res.notes || []).some((n) => String(n).includes("오류")) || !(res.trees || []).length;
  return { nick: p.nick, levels: d.levels || {}, awaken, updatedAt: p.updatedAt,
    resultFor: p.resultFor || "", resultAt: p.resultAt || "", resultOk: Boolean(p.result) && !err };
}

function pub(p) {
  return { nick: p.nick, data: p.data, updatedAt: p.updatedAt, result: p.result, resultFor: p.resultFor, resultAt: p.resultAt };
}

async function getMany(prefix) {
  const nicks = await db().smembers("nicks");
  if (!nicks.length) {
    return [];
  }
  const vals = await db().mget(...nicks.map((n) => prefix + n));
  return vals.filter(Boolean);
}

async function putProfile(prof) {
  const p = db().pipeline();
  p.set("p:" + prof.nick, prof);
  p.set("m:" + prof.nick, summary(prof));
  p.sadd("nicks", prof.nick);
  await p.exec();
}

// 저장 직후 GitHub Actions 분석 실행 요청. 사람(닉네임 해시)마다 따로 실행해 남의 계산을 기다리지 않음
// 같은 사람 10초 안 중복 요청은 생략(계산 작업이 시작할 때 최신 저장본을 다시 읽으므로 빠지는 저장은 없음)
async function dispatch(nick) {
  const token = process.env.GH_TOKEN;
  if (!token) {
    return "no-token";
  }
  const id = createHash("sha1").update(nick, "utf8").digest("hex").slice(0, 10);
  const key = "lastDispatch:" + id;
  const last = Number((await db().get(key)) || 0);
  if (Date.now() - last < 10 * 1000) {
    return "skip";
  }
  const res = await fetch(`https://api.github.com/repos/${GH_REPO}/actions/workflows/${GH_WORKFLOW}/dispatches`, {
    method: "POST",
    headers: { Authorization: "Bearer " + token, Accept: "application/vnd.github+json", "Content-Type": "application/json", "User-Agent": "dosa-api" },
    body: JSON.stringify({ ref: "main", inputs: { id } }),
  });
  if (res.status === 204) {
    await db().set(key, String(Date.now()), { ex: 3600 });
    return "ok";
  }
  return "fail-" + res.status;
}

async function handleGet(p) {
  if (p.a === "load") {
    const nick = cleanNick(p.nick);
    const prof = nick ? await db().get("p:" + nick) : null;
    if (!prof) {
      return out({ ok: false, err: "none" });
    }
    if (prof.pinHash !== hash(nick, String(p.pin || ""))) {
      return out({ ok: false, err: "pin" });
    }
    const [g, picks] = await Promise.all([db().get("g:" + nick), db().hgetall("b:" + nick)]);
    return out({ ok: true, ...pub(prof), data: mergePicks(prof.data, picks), progress: g, now: Date.now() });
  }
  if (p.a === "status") {
    const nick = cleanNick(p.nick);
    const [prof, g] = nick ? await Promise.all([db().get("p:" + nick), db().get("g:" + nick)]) : [null, null];
    if (!prof) {
      return out({ ok: false, err: "none" });
    }
    return out({ ok: true, updatedAt: prof.updatedAt, resultFor: prof.resultFor, resultAt: prof.resultAt, progress: g, now: Date.now() });
  }
  if (p.a === "members") {
    const list = (await getMany("m:")).filter((x) => !MEMBERS_HIDE.includes(x.nick));
    // 분석 진행률(g:)도 함께: 계산 중·대기·완료를 길드원 현황에 표시
    if (list.length) {
      const gs = await db().mget(...list.map((x) => "g:" + x.nick));
      list.forEach((x, i) => { x.progress = gs[i] || null; });
    }
    return out({ ok: true, list, now: Date.now() });
  }
  if (p.a === "data") {
    if (!isAdmin(p.key)) {
      return out({ ok: false, err: "key" });
    }
    const value = await db().get("d:" + String(p.name || ""));
    return out(value === null ? { ok: false, err: "none" } : { ok: true, value });
  }
  if (p.a === "pending" || p.a === "all") {
    if (!isAdmin(p.key)) {
      return out({ ok: false, err: "key" });
    }
    const profs = (await getMany("p:")).filter((x) => p.a === "all" || !x.resultFor || String(x.resultFor) !== String(x.updatedAt));
    let picks = [];
    if (profs.length) {
      const pl = db().pipeline();
      profs.forEach((x) => pl.hgetall("b:" + x.nick));
      picks = await pl.exec();
    }
    return out({ ok: true, list: profs.map((x, i) => forAll(x, picks[i])) });
  }
  return out({ ok: true, service: "dosa" });
}

async function handlePost(b) {
  if (b.a === "save") {
    const nick = cleanNick(b.nick);
    const pin = String(b.pin || "");
    if (!nick || !/^\d{4}$/.test(pin)) {
      return out({ ok: false, err: "input" });
    }
    const data = b.data || {};
    if (JSON.stringify(data).length > MAX_DATA) {
      return out({ ok: false, err: "size" });
    }
    let prof = await db().get("p:" + nick);
    let created = false;
    if (!prof) {
      if (b.create !== true) {
        return out({ ok: false, err: "none" });
      }
      prof = { nick, pinHash: hash(nick, pin), result: null, resultFor: "", resultAt: "" };
      created = true;
    } else if (prof.pinHash !== hash(nick, pin)) {
      return out({ ok: false, err: "pin" });
    }
    const now = String(Date.now());
    prof.data = data;
    prof.updatedAt = now;
    await putProfile(prof);
    let run = "none";
    try {
      run = await dispatch(nick);
    } catch (e) {
      run = "error";
    }
    return out({ ok: true, updatedAt: now, created, run });
  }
  if (b.a === "pick") {
    const nick = cleanNick(b.nick);
    const pin = String(b.pin || "");
    if (!nick || !/^\d{4}$/.test(pin)) {
      return out({ ok: false, err: "input" });
    }
    const ops = pickOps(b);
    if (!ops.ok) {
      return out(ops);
    }
    const prof = await db().get("p:" + nick);
    if (!prof) {
      return out({ ok: false, err: "none" });   // 등록 전이면 만들지 않음(저장을 눌러 등록)
    }
    if (prof.pinHash !== hash(nick, pin)) {
      return out({ ok: false, err: "pin" });
    }
    const key = "b:" + nick;
    const fresh = Object.keys(ops.set).filter((k) => k !== "_style");
    if (fresh.length) {
      const [n, has] = await Promise.all([db().hlen(key), db().hexists(key, fresh[0])]);
      if (!has && n >= MAX_FIELDS) {
        return out({ ok: false, err: "size" });
      }
    }
    const pl = db().pipeline();
    if (Object.keys(ops.set).length) {
      pl.hset(key, ops.set);
    }
    if (ops.del.length) {
      pl.hdel(key, ...ops.del);
    }
    await pl.exec();
    return out({ ok: true });
  }
  if (b.a === "result") {
    if (!isAdmin(b.key)) {
      return out({ ok: false, err: "key" });
    }
    const nick = cleanNick(b.nick);
    const prof = await db().get("p:" + nick);
    if (!prof) {
      return out({ ok: false, err: "none" });
    }
    prof.result = b.result || null;
    prof.resultFor = String(b.updatedAt || "");
    prof.resultAt = String(Date.now());
    await db().set("p:" + nick, prof);
    await db().set("m:" + nick, summary(prof));
    return out({ ok: true });
  }
  if (b.a === "progress") {
    if (!isAdmin(b.key)) {
      return out({ ok: false, err: "key" });
    }
    const nick = cleanNick(b.nick);
    const prev = (await db().get("g:" + nick)) || {};
    const forNow = String(b.updatedAt || "");
    const pct = Math.max(0, Math.min(100, Number(b.pct) || 0));
    // 계산이 실제로 시작된 시각(pct>0 첫 보고)을 남겨 남은 시간을 추정한다
    // 같은 저장분을 다시 계산하면(진행률이 줄어듦) 시작 시각을 새로 잡는다
    const same = prev.for === forNow && prev.start && pct >= (prev.pct || 0);
    const start = same ? prev.start : (pct > 0 ? Date.now() : 0);
    await db().set("g:" + nick, { for: forNow, pct, stage: String(b.stage || ""), at: Date.now(), start }, { ex: 3600 });
    return out({ ok: true });
  }
  if (b.a === "setdata") {
    if (!isAdmin(b.key)) {
      return out({ ok: false, err: "key" });
    }
    await db().set("d:" + String(b.name || ""), b.value);
    return out({ ok: true });
  }
  if (b.a === "resync") {   // 길드원 현황 요약(m:)을 프로필(p:)로 다시 만듦(관리자)
    if (!isAdmin(b.key)) {
      return out({ ok: false, err: "key" });
    }
    const all = await getMany("p:");
    const pl = db().pipeline();
    all.forEach((x) => pl.set("m:" + x.nick, summary(x)));
    if (all.length) {
      await pl.exec();
    }
    return out({ ok: true, n: all.length });
  }
  if (b.a === "import") {
    if (!isAdmin(b.key)) {
      return out({ ok: false, err: "key" });
    }
    const done = [];
    for (const x of b.profiles || []) {
      const nick = cleanNick(x.nick);
      if (!nick) {
        continue;
      }
      await putProfile({
        nick, pinHash: x.pinHash || hash(nick, "0000"), data: x.data || {}, updatedAt: String(x.updatedAt || ""),
        result: x.result || null, resultFor: String(x.resultFor || ""), resultAt: String(x.resultAt || ""),
      });
      done.push(nick);
    }
    return out({ ok: true, done });
  }
  return out({ ok: false, err: "action" });
}

function fail(e) {
  return out({ ok: false, err: "server", msg: String((e && e.message) || e).slice(0, 200) });
}

export function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS });
}

export async function GET(request) {
  try {
    return await handleGet(Object.fromEntries(new URL(request.url).searchParams));
  } catch (e) {
    return fail(e);
  }
}

export async function POST(request) {
  let b = {};
  try {
    b = JSON.parse(await request.text());
  } catch (e) {
    return out({ ok: false, err: "json" });
  }
  try {
    return await handlePost(b);
  } catch (e) {
    return fail(e);
  }
}
