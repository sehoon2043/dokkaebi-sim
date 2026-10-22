// 내 빌드 즉시 저장(pick): 사냥터별 고른 빌드·광역/단일을 Redis 해시 b:<닉네임>에 필드 하나씩 저장한다(재계산 없음).
// 수첩 data를 통째로 다시 쓰지 않아 저장(save)·분석 결과(result) 기록과 서로 덮어쓰지 않고, 다른 기기의 다른 사냥터 선택도 지우지 않는다.
//   필드: <사냥터 키> = 빌드 JSON, _style = {v: "광역"|"단일", at: 바꾼 시각} JSON
// 불러올 때는 해시와 수첩 data(save로 저장된 것) 중 더 최근 것을 쓴다: 서버에 못 간 선택도 [저장]을 누르면 살아난다
export const MAX_BUILD = 4000;   // 빌드 하나 JSON 길이 한도
// 사냥터 키는 정해진 목록만(필드 수가 고정이라 해시를 마구 키우지 못함). 비경 3종 자리 미리 둠, k290~k400은 260k 위 사냥터
export const GROUND_KEYS = ["wild", "well", "mine", "k290", "k310", "k360", "k400", "secret", "secret1", "secret2", "secret3", "boss"];
const STYLES = ["광역", "단일"];

function isObj(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

function parse(v) {
  if (typeof v !== "string") {
    return v;
  }
  try {
    return JSON.parse(v);
  } catch (e) {
    return v;   // 예전 형식 _style("단일") 등
  }
}

// 빌드가 마지막으로 바뀐 시각: 고른 시각과 돌려 본 결과를 적은 시각 중 늦은 것
function stamp(b) {
  return Math.max(Number((b || {}).pickedAt) || 0, Number(((b || {}).result || {}).at) || 0);
}

// 요청 → {ok, set: {필드: 문자열}, del: [필드]} 또는 {ok:false, err:"input"|"size"}
export function pickOps(b) {
  const set = {};
  const del = [];
  if (b.prefStyle !== undefined) {
    if (!STYLES.includes(b.prefStyle)) {
      return { ok: false, err: "input" };
    }
    set._style = JSON.stringify({ v: b.prefStyle, at: Number(b.at) || Date.now() });
  }
  if (b.g !== undefined) {
    if (!GROUND_KEYS.includes(b.g) || !("build" in b)) {
      return { ok: false, err: "input" };
    }
    if (b.build === null) {
      del.push(b.g);
    } else if (isObj(b.build)) {
      const s = JSON.stringify(b.build);
      if (s.length > MAX_BUILD) {
        return { ok: false, err: "size" };
      }
      set[b.g] = s;
    } else {
      return { ok: false, err: "input" };
    }
  }
  if (!Object.keys(set).length && !del.length) {
    return { ok: false, err: "input" };
  }
  return { ok: true, set, del };
}

// 수첩 data + 해시 → 사냥터마다 더 최근 것을 쓴 새 data(원본은 그대로). 목록에 없는 해시 필드는 무시
export function mergePicks(data, hash) {
  if (!hash || !Object.keys(hash).length) {
    return data;
  }
  const d = data || {};
  const out = { ...d, mybuilds: { ...(d.mybuilds || {}) } };
  const st = parse(hash._style);
  if (isObj(st) && STYLES.includes(st.v) && (Number(st.at) || 0) >= (Number(d.prefStyleAt) || 0)) {
    out.prefStyle = st.v;
    out.prefStyleAt = Number(st.at) || 0;
  } else if (STYLES.includes(st) && !d.prefStyleAt) {
    out.prefStyle = st;
  }
  for (const g of GROUND_KEYS) {
    const v = parse(hash[g]);
    if (isObj(v) && stamp(v) >= stamp(out.mybuilds[g])) {
      out.mybuilds[g] = v;
    }
  }
  return out;
}

// 분석용 프로필 목록 한 줄: 결과는 계산 버전만(결과가 커져 목록 응답이 무거워지지 않게), data에는 내 빌드를 합침
export function forAll(p, hash) {
  return {
    nick: p.nick, data: mergePicks(p.data, hash), updatedAt: p.updatedAt,
    result: p.result ? { engine: p.result.engine } : null, resultFor: p.resultFor, resultAt: p.resultAt,
  };
}

// 옮겨 오기·복원(import) 한 줄 → {prof 나머지 값, picks(해시로 되살릴 것 | null)}.
// 결과에 트리가 없으면(줄인 목록으로 받은 백업 등) 다시 계산되게 resultFor를 비운다
export function importPlan(x) {
  const res = x.result || null;
  const full = Boolean(res && Array.isArray(res.trees));
  const picks = isObj(x.picks) ? Object.fromEntries(Object.entries(x.picks).filter(([k]) => k === "_style" || GROUND_KEYS.includes(k))) : null;
  return {
    prof: { data: x.data || {}, updatedAt: String(x.updatedAt || ""), result: full ? res : null,
      resultFor: full ? String(x.resultFor || "") : "", resultAt: full ? String(x.resultAt || "") : "" },
    picks: picks && Object.keys(picks).length ? picks : null,
  };
}
