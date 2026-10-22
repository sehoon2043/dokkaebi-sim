// 내 빌드 즉시 저장(pick) 검사·합치기: node --test server/test/
import { test } from "node:test";
import assert from "node:assert/strict";
import { pickOps, mergePicks, forAll, importPlan, MAX_BUILD, GROUND_KEYS } from "../lib/pick.js";

const build = { tier: "딜", style: "광역", from: "calc", order: ["a", "b"], ult: "b", slots: ["a"], pickedAt: 1 };

test("사냥터 하나의 빌드를 그 필드에만 저장", () => {
  const r = pickOps({ g: "well", build });
  assert.equal(r.ok, true);
  assert.deepEqual(Object.keys(r.set), ["well"]);
  assert.deepEqual(JSON.parse(r.set.well), build);
  assert.deepEqual(r.del, []);
});

test("광역/단일은 _style 필드에 바꾼 시각과 함께, 두 값만 허용", () => {
  assert.deepEqual(JSON.parse(pickOps({ prefStyle: "단일", at: 7 }).set._style), { v: "단일", at: 7 });
  assert.equal(pickOps({ prefStyle: "전부" }).err, "input");
});

test("사냥터 키는 정해진 목록만(해시를 마구 키우지 못하게)", () => {
  for (const g of GROUND_KEYS) {
    assert.equal(pickOps({ g, build }).ok, true);
  }
  assert.equal(pickOps({ g: "abc", build }).err, "input");
  assert.equal(pickOps({ g: "well2", build }).err, "input");
});

test("수첩 data가 더 최근이면 data가 이김(서버에 못 간 선택을 저장 버튼으로 살림)", () => {
  const newer = { ...build, pickedAt: 9 };
  const out = mergePicks({ mybuilds: { well: newer }, prefStyle: "광역", prefStyleAt: 9 },
    { well: JSON.stringify({ ...build, pickedAt: 2 }), _style: JSON.stringify({ v: "단일", at: 2 }) });
  assert.equal(out.mybuilds.well.pickedAt, 9);
  assert.equal(out.prefStyle, "광역");
});

test("돌려 본 결과를 고친 시각도 최신 판단에 씀", () => {
  const edited = { ...build, pickedAt: 1, result: { coinPerMin: 720, at: 50 } };
  const out = mergePicks({ mybuilds: { well: edited } }, { well: JSON.stringify({ ...build, pickedAt: 10 }) });
  assert.equal(out.mybuilds.well.result.coinPerMin, 720);
});

test("목록에 없는 해시 필드는 무시", () => {
  const out = mergePicks({}, { zzz: JSON.stringify(build) });
  assert.equal("zzz" in (out.mybuilds || {}), false);
});

test("build가 null이면 그 사냥터 빌드를 지움", () => {
  const r = pickOps({ g: "well", build: null });
  assert.deepEqual(r.del, ["well"]);
  assert.deepEqual(r.set, {});
});

test("이상한 입력은 input", () => {
  assert.equal(pickOps({}).err, "input");
  assert.equal(pickOps({ g: "well", build: [1] }).err, "input");
  assert.equal(pickOps({ g: "Well!", build }).err, "input");
  assert.equal(pickOps({ g: "_style", build }).err, "input");
  assert.equal(pickOps({ g: "well" }).err, "input");
});

test("너무 큰 빌드는 size", () => {
  const big = { ...build, memo: "x".repeat(MAX_BUILD) };
  assert.equal(pickOps({ g: "well", build: big }).err, "size");
});

test("불러올 때 해시를 수첩 data에 합침(해시가 더 최근이면 이김, 원본은 그대로)", () => {
  const data = { levels: { 절명: 45 }, prefStyle: "광역", mybuilds: { well: { tier: "생존" }, mine: { tier: "믹스" } } };
  const out = mergePicks(data, { well: JSON.stringify(build), _style: JSON.stringify({ v: "단일", at: 3 }), boss: "{깨진" });
  assert.equal(out.prefStyle, "단일");
  assert.deepEqual(out.mybuilds.well, build);
  assert.deepEqual(out.mybuilds.mine, { tier: "믹스" });
  assert.equal(out.levels.절명, 45);
  assert.equal("boss" in out.mybuilds, false);
  assert.equal(data.mybuilds.well.tier, "생존");
});

test("해시 값이 이미 객체여도(Upstash 자동 변환) 합침", () => {
  const out = mergePicks({}, { well: build });
  assert.deepEqual(out.mybuilds.well, build);
});

test("해시가 없으면 data 그대로", () => {
  const data = { levels: {} };
  assert.deepEqual(mergePicks(data, null), data);
});

test("분석용 목록은 결과 대신 계산 버전만(응답 크기)", () => {
  const p = { nick: "n", data: { a: 1 }, updatedAt: "2", result: { engine: "e1", trees: [1, 2], decks: { x: 1 } }, resultFor: "2", resultAt: "3", pinHash: "h" };
  const x = forAll(p, { well: JSON.stringify(build) });
  assert.deepEqual(x.result, { engine: "e1" });
  assert.deepEqual(x.data.mybuilds.well, build);
  assert.equal(x.resultAt, "3");
  assert.equal("pinHash" in x, false);
  assert.equal(forAll({ ...p, result: null }, null).result, null);
});

test("복원(import): 결과에 트리가 없으면 다시 계산되게, 해시는 지우거나 함께 넘긴 것으로", () => {
  const x = { nick: "n", data: { owned: { a: {} } }, updatedAt: "5", result: { engine: "e" }, resultFor: "5", resultAt: "6" };
  const p = importPlan(x);
  assert.equal(p.prof.resultFor, "");
  assert.equal(p.prof.result, null);
  assert.deepEqual(p.picks, null);
  const full = importPlan({ ...x, result: { engine: "e", trees: [1] }, picks: { well: JSON.stringify(build) } });
  assert.equal(full.prof.resultFor, "5");
  assert.deepEqual(Object.keys(full.picks), ["well"]);
});
