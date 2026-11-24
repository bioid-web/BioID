// Per-tube TzKT reads (v0.4): a fake TzKT served from the recorded Shadownet
// fixtures must give the same tube view as reading the whole contract.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { NETWORKS } from "../config.js";
import { effectiveStatus, loadIndexes, resolveLookup, viewToken } from "../src/parse.js";
import { loadTube } from "../src/tzkt.js";

const fixtureDir = fileURLToPath(new URL("../fixtures/shadownet/", import.meta.url));
const read = (name) => JSON.parse(readFileSync(path.join(fixtureDir, name), "utf8"));
const fixture = {
  storage: read("storage.json"),
  codeIndex: read("code_index.json"),
  tokens: read("tokens.json"),
  wallets: read("wallets.json"),
  attachments: read("attachments.json"),
  transactions: read("transactions.json"),
  events: read("events.json"),
};
const network = NETWORKS.shadownet;
const maps = {
  [fixture.storage.code_index]: fixture.codeIndex,
  [fixture.storage.tokens]: fixture.tokens,
  [fixture.storage.wallet_registry]: fixture.wallets,
  [fixture.storage.attachments]: fixture.attachments,
};

function fakeTzkt() {
  const calls = [];
  const reply = (body, status = 200) => ({ ok: status < 300, status, json: async () => body });
  const fetchImpl = async (raw) => {
    calls.push(raw);
    const url = new URL(raw);
    const parts = url.pathname.replace(/^\/v1\//, "").split("/");
    const q = url.searchParams;
    if (parts[0] === "contracts" && parts[2] === "storage") return reply(fixture.storage);
    if (parts[0] === "bigmaps" && parts[2] === "keys" && parts.length === 4) {
      const row = (maps[parts[1]] || []).find((item) => String(item.key) === decodeURIComponent(parts[3]));
      return row ? reply(row) : reply(null, 204);
    }
    if (parts[0] === "bigmaps" && parts[2] === "keys") {
      const parent = q.get("value.parent_id");
      return reply((maps[parts[1]] || []).filter((row) => row.value && row.value.parent_id != null && String(row.value.parent_id) === parent));
    }
    if (parts[0] === "contracts" && parts[1] === "events") {
      let rows = fixture.events;
      for (const field of ["token_id", "code", "root"]) {
        const value = q.get(`payload.${field}`);
        if (value != null) rows = rows.filter((event) => event.payload && String(event.payload[field]) === value);
      }
      return reply(rows);
    }
    if (parts[0] === "operations" && parts[1] === "transactions") {
      const ids = new Set((q.get("id.in") || "").split(","));
      return reply(fixture.transactions.filter((row) => ids.has(String(row.id))));
    }
    throw new Error(`unexpected URL ${raw}`);
  };
  return { fetchImpl, calls };
}

const full = loadIndexes({ ...fixture, explorer: network.explorer });

async function tubeIndexes(lookup) {
  const { fetchImpl, calls } = fakeTzkt();
  const raw = await loadTube(network, lookup, { fetchImpl, sleep: async () => {} });
  return { calls, indexes: loadIndexes({ ...raw, explorer: network.explorer }) };
}

for (const code of ["SY00000221", "SY00000241", "SY00000201", "SY00000212"]) {
  test(`per-tube read of ${code} matches the whole-contract view`, async () => {
    const { indexes, calls } = await tubeIndexes({ kind: "code", code });
    const resolved = resolveLookup({ kind: "code", code }, indexes.codeIndex, indexes.tokens);
    assert.equal(resolved.status, "token");
    const one = viewToken(resolved.tokenId, indexes);
    const all = viewToken(resolved.tokenId, full);
    assert.deepEqual(one.token, all.token);
    assert.deepEqual(one.parents, all.parents);
    assert.deepEqual(one.children, all.children);
    assert.deepEqual(one.datasets, all.datasets);
    assert.deepEqual(one.wallet, all.wallet);
    assert.deepEqual(one.timeline, all.timeline);
    // No full-bigmap scans: every keys call is a single key or a value filter.
    for (const url of calls) {
      if (url.includes("/keys") && !url.includes("/keys/")) assert.match(url, /value\.parent_id=/);
      if (url.includes("/contracts/events")) assert.match(url, /payload\.(token_id|code|root)=/);
    }
  });
}

test("per-tube read by token id works without the code index", async () => {
  const { indexes } = await tubeIndexes({ kind: "token", tokenId: "8" });
  assert.equal(viewToken("8", indexes).token.code, "SY00000241");
});

test("an unknown code gives an empty, not invented, result", async () => {
  const { indexes } = await tubeIndexes({ kind: "code", code: "SY00000999" });
  assert.equal(resolveLookup({ kind: "code", code: "SY00000999" }, indexes.codeIndex, indexes.tokens).status, "missing");
});

test("effective status follows the root withdrawal (v0.4 constant-cost freeze)", () => {
  const token = { status: "active", destroyed: false };
  const ev = (tag, payload) => ({ tag, payload });
  assert.equal(effectiveStatus(token, "SY00000201", []), "active");
  assert.equal(effectiveStatus(token, "SY00000201", [ev("WITHDRAW", { root: "SY00000202", outcome: "destroy" })]), "active");
  assert.equal(effectiveStatus(token, "SY00000201", [ev("WITHDRAW", { root: "SY00000201", outcome: "stop_use" })]), "stopped");
  assert.equal(
    effectiveStatus(token, "SY00000201", [
      ev("WITHDRAW", { root: "SY00000201", outcome: "stop_use" }),
      ev("WITHDRAW", { root: "SY00000201", outcome: "destroy", previous: "stop_use" }),
    ]),
    "frozen",
  );
  assert.equal(
    effectiveStatus(token, "SY00000201", [
      ev("WITHDRAW", { root: "SY00000201", outcome: "anonymise" }),
      ev("UNFREEZE", { root: "SY00000201" }),
    ]),
    "anonymised",
  );
  assert.equal(effectiveStatus({ status: "frozen", destroyed: true }, "SY00000201", []), "destroyed");
});
