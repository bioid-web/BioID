// Read-only TzKT client. Bigmap pointers come from contract storage
// so a re-origination does not require a code change.

import { bigmapPointer } from "./parse.js";

const RETRYABLE_STATUS = new Set([408, 425, 429, 500, 502, 503, 504]);

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Public indexers and RPC nodes return transient errors (white paper, section 4).
// Retry network failures, timeouts, 429 and 5xx with exponential backoff. A 404 or
// other 4xx is a real answer and is not retried. `options` exists so tests can
// inject fetch and a no-op sleep.
export async function fetchJson(url, options = {}) {
  const {
    retries = 3,
    timeoutMs = 15000,
    baseDelayMs = 400,
    fetchImpl = globalThis.fetch,
    sleep = delay,
  } = options;
  let lastError;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetchImpl(url, { signal: controller.signal });
      // TzKT answers 204 with an empty body for a bigmap key that does not exist.
      if (response.status === 204) return null;
      if (response.ok) return await response.json();
      lastError = new Error(`TzKT answered ${response.status} for ${url}`);
      lastError.status = response.status;
      if (!RETRYABLE_STATUS.has(response.status)) throw lastError;
    } catch (error) {
      if (error === lastError && !RETRYABLE_STATUS.has(error.status)) throw error;
      lastError = error.name === "AbortError"
        ? new Error(`TzKT did not answer within ${timeoutMs} ms for ${url}`)
        : error;
    } finally {
      clearTimeout(timer);
    }
    if (attempt < retries) await sleep(baseDelayMs * 2 ** attempt);
  }
  throw lastError;
}

async function collect(url, pageSize = 100) {
  const rows = [];
  let offset = 0;
  for (;;) {
    const joiner = url.includes("?") ? "&" : "?";
    const page = await fetchJson(`${url}${joiner}limit=${pageSize}&offset=${offset}`);
    if (!Array.isArray(page)) throw new Error("TzKT did not return a list");
    rows.push(...page);
    if (page.length < pageSize) return rows;
    offset += pageSize;
  }
}

export async function loadContract(network) {
  if (!network || !network.contract) {
    throw new Error("No contract is configured for this network.");
  }
  const api = network.api.replace(/\/$/, "");
  const storage = await fetchJson(`${api}/contracts/${network.contract}/storage`);
  const pointer = (name) => {
    const id = bigmapPointer(storage, name);
    if (!id) throw new Error(`Contract storage has no ${name} bigmap`);
    return id;
  };
  const [codeIndex, tokens, wallets, attachments, events, transactions] = await Promise.all([
    collect(`${api}/bigmaps/${pointer("code_index")}/keys`),
    collect(`${api}/bigmaps/${pointer("tokens")}/keys`),
    collect(`${api}/bigmaps/${pointer("wallet_registry")}/keys`),
    collect(`${api}/bigmaps/${pointer("attachments")}/keys`),
    collect(`${api}/contracts/events?contract=${network.contract}&sort.asc=id`),
    collect(`${api}/operations/transactions?target=${network.contract}&status=applied&sort.asc=id`),
  ]);
  return { storage, codeIndex, tokens, wallets, attachments, events, transactions };
}

// Per-tube read (v0.4). Loading every bigmap key and every event is fine for a
// pilot but grows with the contract. For one scanned tube, ask TzKT only for
// that tube: its code_index entry, its token row, its ancestors (one key each,
// at most 8 generations), its children (value filter), the attachments of the
// tube and its ancestors, the wallets they sit in, and the events that name the
// tube or its root. The result has the same shape as loadContract, so the parser
// does not change. `options` lets tests inject fetch.
export const MAX_GENERATIONS = 8;

export async function loadTube(network, lookup, options = {}) {
  if (!network || !network.contract) {
    throw new Error("No contract is configured for this network.");
  }
  const api = network.api.replace(/\/$/, "");
  const get = (url) => fetchJson(url, { ...options });
  const list = async (url) => {
    const rows = await get(url);
    return Array.isArray(rows) ? rows : [];
  };
  const storage = await get(`${api}/contracts/${network.contract}/storage`);
  const pointer = (name) => {
    const id = bigmapPointer(storage, name);
    if (!id) throw new Error(`Contract storage has no ${name} bigmap`);
    return id;
  };
  const enc = encodeURIComponent;
  const empty = { storage, codeIndex: [], tokens: [], wallets: [], attachments: [], events: [], transactions: [] };

  const codeIndex = [];
  let tokenId = null;
  if (lookup && lookup.kind === "code") {
    const row = await get(`${api}/bigmaps/${pointer("code_index")}/keys/${enc(lookup.code)}`);
    if (!row || row.active === false) return empty;
    codeIndex.push(row);
    tokenId = String(row.value);
  } else if (lookup && lookup.kind === "token") {
    tokenId = String(lookup.tokenId);
  } else {
    return empty;
  }

  const tokensMap = pointer("tokens");
  const tokenRow = (id) => get(`${api}/bigmaps/${tokensMap}/keys/${enc(id)}`);
  const self = await tokenRow(tokenId);
  if (!self || self.active === false) return { ...empty, codeIndex };
  const tokens = [self];
  const ancestors = [];
  let cursor = self.value && self.value.parent_id != null ? String(self.value.parent_id) : null;
  const seen = new Set([tokenId]);
  while (cursor && !seen.has(cursor) && ancestors.length < MAX_GENERATIONS) {
    seen.add(cursor);
    const row = await tokenRow(cursor);
    if (!row) break;
    tokens.push(row);
    ancestors.push(row);
    cursor = row.value && row.value.parent_id != null ? String(row.value.parent_id) : null;
  }
  const children = await list(`${api}/bigmaps/${tokensMap}/keys?active=true&value.parent_id=${enc(tokenId)}&limit=1000`);
  tokens.push(...children);

  const rootId = String((self.value && self.value.root_id) ?? tokenId);
  const rootRow = tokens.find((row) => String(row.key) === rootId) || (await tokenRow(rootId));
  if (rootRow && !tokens.includes(rootRow)) tokens.push(rootRow);
  const code = self.value.code;
  const rootCode = (rootRow && rootRow.value && rootRow.value.code) || code;

  const lineageIds = [tokenId, ...ancestors.map((row) => String(row.key))];
  const attachMap = pointer("attachments");
  const walletMap = pointer("wallet_registry");
  const addresses = [...new Set(tokens.map((row) => row.value && row.value.wallet).filter(Boolean))];
  const contract = network.contract;
  const [attachments, wallets, byId, byCode, byRoot] = await Promise.all([
    Promise.all(lineageIds.map((id) => get(`${api}/bigmaps/${attachMap}/keys/${enc(id)}`))),
    Promise.all(addresses.map((address) => get(`${api}/bigmaps/${walletMap}/keys/${enc(address)}`))),
    list(`${api}/contracts/events?contract=${contract}&payload.token_id=${enc(tokenId)}&sort.asc=id&limit=1000`),
    list(`${api}/contracts/events?contract=${contract}&payload.code=${enc(code)}&sort.asc=id&limit=1000`),
    list(`${api}/contracts/events?contract=${contract}&payload.root=${enc(rootCode)}&sort.asc=id&limit=1000`),
  ]);
  const events = [];
  const eventIds = new Set();
  for (const event of [...byId, ...byCode, ...byRoot]) {
    if (!event || eventIds.has(event.id)) continue;
    eventIds.add(event.id);
    events.push(event);
  }
  events.sort((a, b) => a.id - b.id);
  // The timeline names every wallet the tube passed through, not only where it is now.
  const fetched = new Set(addresses);
  const passed = [...new Set(events.map((event) => event.payload && event.payload.to_).filter(Boolean))]
    .filter((address) => !fetched.has(address));
  const earlier = await Promise.all(passed.map((address) => get(`${api}/bigmaps/${walletMap}/keys/${enc(address)}`)));
  wallets.push(...earlier);
  const txIds = [...new Set(events.map((event) => event.transactionId).filter((id) => id != null))];
  const transactions = [];
  for (let i = 0; i < txIds.length; i += 50) {
    const chunk = txIds.slice(i, i + 50).join(",");
    transactions.push(...(await list(`${api}/operations/transactions?id.in=${chunk}&select=id,hash,timestamp&limit=50`)));
  }
  return {
    storage,
    codeIndex,
    tokens,
    wallets: wallets.filter(Boolean),
    attachments: attachments.filter(Boolean),
    events,
    transactions,
  };
}
