// 내 빌드 즉시 저장(pick): 사냥터별 고른 빌드·광역/단일을 Redis 해시 b:<닉네임>에 필드 하나씩 저장한다(재계산 없음).
// 수첩 data를 통째로 다시 쓰지 않아 저장(save)·분석 결과(result) 기록과 서로 덮어쓰지 않고, 다른 기기의 다른 사냥터 선택도 지우지 않는다.
//   필드: <사냥터 키> = 빌드 JSON, _style = "광역" | "단일"
export const MAX_BUILD = 4000;   // 빌드 하나 JSON 길이 한도
export const MAX_FIELDS = 20;    // 해시 필드 수 한도(사냥터 키를 마음대로 늘리지 못하게)
const STYLES = ["광역", "단일"];
const GKEY = /^[a-z][a-z0-9_]{0,15}$/;

function isObj(v) {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

// 요청 → {ok, set: {필드: 문자열}, del: [필드]} 또는 {ok:false, err:"input"|"size"}
export function pickOps(b) {
  const set = {};
  const del = [];
  if (b.prefStyle !== undefined) {
    if (!STYLES.includes(b.prefStyle)) {
      return { ok: false, err: "input" };
    }
    set._style = b.prefStyle;
  }
  if (b.g !== undefined) {
    if (typeof b.g !== "string" || !GKEY.test(b.g) || !("build" in b)) {
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

// 수첩 data + 해시 → 해시의 빌드·광역/단일이 이긴 새 data(원본은 그대로)
export function mergePicks(data, hash) {
  if (!hash || !Object.keys(hash).length) {
    return data;
  }
  const out = { ...(data || {}), mybuilds: { ...((data || {}).mybuilds || {}) } };
  for (const [k, v] of Object.entries(hash)) {
    if (k === "_style") {
      if (STYLES.includes(v)) {
        out.prefStyle = v;
      }
      continue;
    }
    let val = v;
    if (typeof v === "string") {
      try {
        val = JSON.parse(v);
      } catch (e) {
        continue;
      }
    }
    if (isObj(val)) {
      out.mybuilds[k] = val;
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
