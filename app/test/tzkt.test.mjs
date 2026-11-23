import test from "node:test";
import assert from "node:assert/strict";
import { fetchJson } from "../src/tzkt.js";

const noSleep = async () => {};
const ok = (body) => ({ ok: true, status: 200, json: async () => body });
const fail = (status) => ({ ok: false, status, json: async () => ({}) });

function scripted(...steps) {
  const calls = [];
  const fetchImpl = async (url) => {
    calls.push(url);
    const step = steps.shift();
    if (step instanceof Error) throw step;
    return step;
  };
  return { fetchImpl, calls };
}

test("retries a 503 and then succeeds", async () => {
  const { fetchImpl, calls } = scripted(fail(503), fail(502), ok([1]));
  const result = await fetchJson("https://x/y", { fetchImpl, sleep: noSleep });
  assert.deepEqual(result, [1]);
  assert.equal(calls.length, 3);
});

test("retries a network error", async () => {
  const { fetchImpl, calls } = scripted(new TypeError("fetch failed"), ok({ a: 1 }));
  assert.deepEqual(await fetchJson("https://x/y", { fetchImpl, sleep: noSleep }), { a: 1 });
  assert.equal(calls.length, 2);
});

test("does not retry a 404", async () => {
  const { fetchImpl, calls } = scripted(fail(404), ok([]));
  await assert.rejects(fetchJson("https://x/y", { fetchImpl, sleep: noSleep }), /404/);
  assert.equal(calls.length, 1);
});

test("gives up after the retry budget and reports the last status", async () => {
  const { fetchImpl, calls } = scripted(fail(500), fail(500), fail(500), fail(429));
  await assert.rejects(fetchJson("https://x/y", { fetchImpl, sleep: noSleep }), /429/);
  assert.equal(calls.length, 4);
});

test("backs off exponentially", async () => {
  const waits = [];
  const { fetchImpl } = scripted(fail(500), fail(500), fail(500), ok([]));
  await fetchJson("https://x/y", {
    fetchImpl,
    baseDelayMs: 100,
    sleep: async (ms) => waits.push(ms),
  });
  assert.deepEqual(waits, [100, 200, 400]);
});

test("a hung request is aborted and retried", async () => {
  let n = 0;
  const fetchImpl = (url, { signal }) => {
    n += 1;
    if (n === 1) {
      return new Promise((_, reject) =>
        signal.addEventListener("abort", () => reject(Object.assign(new Error("aborted"), { name: "AbortError" })))
      );
    }
    return Promise.resolve(ok(["done"]));
  };
  const result = await fetchJson("https://x/y", { fetchImpl, sleep: noSleep, timeoutMs: 20 });
  assert.deepEqual(result, ["done"]);
  assert.equal(n, 2);
});
