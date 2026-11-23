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
