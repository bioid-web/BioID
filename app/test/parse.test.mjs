import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PILOT_CODES, NETWORKS, DEFAULT_NETWORK } from "../config.js";
import {
  bigmapPointer,
  eventTouches,
  formatTimestamp,
  loadIndexes,
  parseScan,
  resolveLookup,
  tubeUrl,
  viewToken,
} from "../src/parse.js";

const fixtureDir = fileURLToPath(new URL("../fixtures/shadownet/", import.meta.url));

function read(name) {
  return JSON.parse(readFileSync(path.join(fixtureDir, name), "utf8"));
}

const indexes = loadIndexes({
  codeIndex: read("code_index.json"),
  tokens: read("tokens.json"),
  wallets: read("wallets.json"),
  attachments: read("attachments.json"),
  transactions: read("transactions.json"),
  events: read("events.json"),
  explorer: "https://shadownet.tzkt.io",
});

test("recorded storage pointers match the Shadownet deployment", () => {
  const storage = read("storage.json");
  assert.equal(bigmapPointer(storage, "code_index"), "40752");
  assert.equal(bigmapPointer(storage, "tokens"), "40761");
  assert.equal(bigmapPointer(storage, "wallet_registry"), "40762");
  assert.equal(bigmapPointer(storage, "attachments"), "40750");
  assert.equal(bigmapPointer({ tokens: { id: 9 } }, "tokens"), "9");
});

test("pilot codes in config match the recorded code index", () => {
  const recorded = [...indexes.codeIndex.keys()].sort();
  assert.deepEqual(recorded, [...PILOT_CODES].sort());
  assert.equal(DEFAULT_NETWORK, "shadownet");
  assert.equal(NETWORKS.shadownet.contract, "KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix");
  assert.equal(NETWORKS.mainnet.contract, "");
  assert.equal(NETWORKS.mainnet.readOnly, true);
});

test("scan text accepts a deep link, a tube code, or a token id", () => {
  assert.deepEqual(parseScan("https://example.org/app/?tube=SY00000221"), {
    kind: "code",
    code: "SY00000221",
  });
  assert.deepEqual(parseScan("https://example.org/app/index.html?token=8"), {
    kind: "token",
    tokenId: "8",
  });
  assert.deepEqual(parseScan("sy00000241"), { kind: "code", code: "SY00000241" });
  assert.deepEqual(parseScan("5"), { kind: "token", tokenId: "5" });
  assert.equal(parseScan("not a tube").kind, "unknown");
  assert.equal(parseScan("  ").kind, "empty");
});

test("tube links keep the configurable base and set ?tube=", () => {
  assert.equal(
    tubeUrl("https://example.org/bioid/app/", "SY00000221"),
    "https://example.org/bioid/app/?tube=SY00000221",
  );
  assert.equal(
    tubeUrl("https://example.org/bioid/app/index.html", "SY00000221"),
    "https://example.org/bioid/app/index.html?tube=SY00000221",
  );
});

test("SY00000221 resolves to the external user, 600 µL, and its consume operation", () => {
  const resolved = resolveLookup({ kind: "code", code: "SY00000221" }, indexes.codeIndex, indexes.tokens);
  assert.equal(resolved.tokenId, "5");
  const view = viewToken(resolved.tokenId, indexes);
  assert.equal(view.token.code, "SY00000221");
  assert.equal(view.token.balanceUl, "600");
  assert.equal(view.token.sampleType, "aliquot");
  assert.equal(view.wallet.label, "SYN-PILOT-EXT");
  assert.equal(view.wallet.type, "EXTERNAL_USER");
  assert.equal(view.parents.length, 1);
  assert.equal(view.parents[0].code, "SY00000202");
  assert.equal(view.children.length, 0);
  assert.equal(view.datasets.own.length, 1);
  assert.equal(view.datasets.own[0].type, "analysis");
  assert.equal(view.datasets.own[0].inherited, false);
  assert.equal(view.datasets.inherited.length, 0);
  const tags = view.timeline.map((event) => event.tag);
  for (const tag of ["MINT", "MOVE", "SHIP", "RECEIVE", "ACCESS_REQUEST", "ACCESS_APPROVED", "CONSUME", "DATA_ATTACHED"]) {
    assert.ok(tags.includes(tag), tag);
  }
  const consume = view.timeline.find((event) => event.tag === "CONSUME");
  assert.equal(consume.hash, "ooy57ERYhkvJBYMMSVLeeCU4TuXWQJ63Ayfe9nbtkeF8yEXbUoq");
  assert.equal(
    consume.explorer,
    "https://shadownet.tzkt.io/ooy57ERYhkvJBYMMSVLeeCU4TuXWQJ63Ayfe9nbtkeF8yEXbUoq",
  );
  assert.match(consume.summary, /400 µL/);
  assert.match(consume.summary, /balance 600 µL/);
  const times = view.timeline.map((event) => event.timestamp);
  assert.deepEqual(times, [...times].sort());
});

test("RNA child SY00000241 inherits ancestor datasets and keeps its own parent chain", () => {
  const view = viewToken("8", indexes);
  assert.equal(view.token.code, "SY00000241");
  assert.equal(view.token.balanceUl, "80");
  assert.equal(view.token.sampleType, "RNA");
  assert.equal(view.wallet.label, "SYN-PILOT-LT80");
  assert.equal(view.wallet.type, "STORAGE");
  assert.deepEqual(view.parents.map((token) => token.code), ["SY00000212", "SY00000201"]);
  assert.equal(view.datasets.own.length, 0);
  assert.equal(view.datasets.inherited.length, 3);
  assert.ok(view.datasets.inherited.every((row) => row.inherited));
  assert.equal(view.datasets.inherited[0].fromCode, "SY00000212");
  assert.equal(view.datasets.inherited[0].type, "rin");
  assert.match(view.datasets.inherited[0].uri, /SY00000241/);
  assert.equal(view.datasets.inherited[0].sha256.length, 64);
  const fromRoot = view.datasets.inherited.filter((row) => row.fromCode === "SY00000201");
  assert.equal(fromRoot.length, 2);
  assert.ok(fromRoot.every((row) => row.type === "qc"));
});

test("primary tube lists its children", () => {
  const view = viewToken("0", indexes);
  assert.deepEqual(view.children.map((token) => token.code), ["SY00000211", "SY00000212"]);
  assert.equal(view.token.balanceUl, "0");
  assert.equal(view.parents.length, 0);
});

test("an unknown code does not invent a token", () => {
  const resolved = resolveLookup({ kind: "code", code: "SY00000999" }, indexes.codeIndex, indexes.tokens);
  assert.equal(resolved.status, "missing");
});

test("withdrawal and unfreeze follow the root code even though this deployment did not emit them", () => {
  const token = { id: "3", code: "SY00000211" };
  const withdraw = { tag: "WITHDRAW", payload: { root: "SY00000201", outcome: "destroy" } };
  const other = { tag: "WITHDRAW", payload: { root: "SY00000202", outcome: "destroy" } };
  const unfreeze = { tag: "UNFREEZE", payload: { root: "SY00000201" } };
  assert.equal(eventTouches(withdraw, token, "SY00000201"), true);
  assert.equal(eventTouches(other, token, "SY00000201"), false);
  assert.equal(eventTouches(unfreeze, token, "SY00000201"), true);
  const destroyed = { tag: "DESTROYED", payload: { token_id: "3", code: "SY00000211", reason: "withdrawn-destroyed" } };
  assert.equal(eventTouches(destroyed, token, "SY00000201"), true);
});

test("timestamps can be formatted in a chosen zone", () => {
  const text = formatTimestamp("2026-10-19T17:27:18Z", { locale: "en-GB", timeZone: "UTC" });
  assert.match(text, /2026/);
  assert.match(text, /17:27/);
});
