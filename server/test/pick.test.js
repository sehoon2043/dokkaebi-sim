// 내 빌드 즉시 저장(pick) 검사·합치기: node --test server/test/
import { test } from "node:test";
import assert from "node:assert/strict";
import { pickOps, mergePicks, forAll, MAX_BUILD } from "../lib/pick.js";

const build = { tier: "딜", style: "광역", from: "calc", order: ["a", "b"], ult: "b", slots: ["a"], pickedAt: 1 };

test("사냥터 하나의 빌드를 그 필드에만 저장", () => {
  const r = pickOps({ g: "well", build });
  assert.equal(r.ok, true);
  assert.deepEqual(Object.keys(r.set), ["well"]);
  assert.deepEqual(JSON.parse(r.set.well), build);
  assert.deepEqual(r.del, []);
});

test("광역/단일은 _style 필드, 두 값만 허용", () => {
  assert.deepEqual(pickOps({ prefStyle: "단일" }).set, { _style: "단일" });
  assert.equal(pickOps({ prefStyle: "전부" }).err, "input");
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

test("불러올 때 해시를 수첩 data에 합침(해시가 이김, 원본은 그대로)", () => {
  const data = { levels: { 절명: 45 }, prefStyle: "광역", mybuilds: { well: { tier: "생존" }, mine: { tier: "믹스" } } };
  const out = mergePicks(data, { well: JSON.stringify(build), _style: "단일", bad: "{깨진" });
  assert.equal(out.prefStyle, "단일");
  assert.deepEqual(out.mybuilds.well, build);
  assert.deepEqual(out.mybuilds.mine, { tier: "믹스" });
  assert.equal(out.levels.절명, 45);
  assert.equal("bad" in out.mybuilds, false);
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
