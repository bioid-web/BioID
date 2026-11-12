// Read-only TzKT client. Bigmap pointers come from contract storage
// so a re-origination does not require a code change.

import { bigmapPointer } from "./parse.js";

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`TzKT answered ${response.status} for ${url}`);
  }
  return response.json();
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
