// Pure TzKT parsing and lineage. No network, no DOM.

export const EVENT_LABELS = {
  MINT: "Mint",
  MOVE: "Move",
  TRANSFORM: "Transform",
  SHIP: "Ship",
  RECEIVE: "Receive",
  CONSUME: "Consume",
  DATA_ATTACHED: "Dataset attached",
  ACCESS_REQUEST: "Access request",
  ACCESS_APPROVED: "Access approval",
  USE_REPORTED: "Use reported",
  ADJUST: "Volume adjusted",
  WITHDRAW: "Withdrawal",
  DESTROYED: "Destroyed",
  UNFREEZE: "Unfrozen",
};

const LINEAGE_TAGS = new Set(["WITHDRAW", "UNFREEZE"]);

export function bigmapPointer(storage, name) {
  const value = storage ? storage[name] : undefined;
  if (typeof value === "number" || typeof value === "string") return String(value);
  if (value && typeof value === "object" && value.id != null) return String(value.id);
  return null;
}

export function indexRows(rows) {
  const map = new Map();
  for (const row of rows || []) {
    if (!row || row.active === false) continue;
    map.set(String(row.key), row.value);
  }
  return map;
}

export function indexTransactions(rows) {
  const map = new Map();
  for (const row of rows || []) {
    if (row && row.id != null) map.set(String(row.id), row);
  }
  return map;
}

export function shortAddress(address) {
  const text = String(address || "");
  if (text.length < 12) return text;
  return `${text.slice(0, 6)}…${text.slice(-4)}`;
}

export function humanStatus(status) {
  return String(status || "").replaceAll("_", " ");
}

export function parseScan(raw) {
  const text = String(raw || "").trim();
  if (!text) return { kind: "empty" };
  const fromUrl = lookupFromUrl(text);
  if (fromUrl) return fromUrl;
  if (/^SY\d+$/i.test(text)) return { kind: "code", code: text.toUpperCase() };
  if (/^\d+$/.test(text)) return { kind: "token", tokenId: String(BigInt(text)) };
  return { kind: "unknown", raw: text };
}

export function lookupFromQuery(params) {
  const tube = params.get("tube");
  const token = params.get("token");
  if (tube && tube.trim()) return { kind: "code", code: tube.trim().toUpperCase() };
  if (token && token.trim()) {
    const trimmed = token.trim();
    if (/^\d+$/.test(trimmed)) return { kind: "token", tokenId: String(BigInt(trimmed)) };
    return { kind: "unknown", raw: trimmed };
  }
  return { kind: "empty" };
}

function lookupFromUrl(text) {
  let url;
  try {
    url = new URL(text);
  } catch {
    return null;
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return null;
  return lookupFromQuery(url.searchParams);
}

export function tubeUrl(base, code) {
  const url = new URL(String(base).trim());
  url.searchParams.set("tube", code);
  url.hash = "";
  return url.href;
}

export function describeWallet(address, registry) {
  const row = address && registry ? registry.get(address) : null;
  return {
    address: address || "",
    label: (row && row.label) || (address ? shortAddress(address) : "Unknown wallet"),
    type: (row && row.type) || "",
    site: (row && row.site) || "",
    process: (row && row.process) || "",
    active: row ? row.active !== false : false,
    known: Boolean(row),
  };
}

export function asToken(id, value) {
  const parent = value.parent_id;
  return {
    id: String(id),
    code: value.code || "",
    status: value.status || "",
    balanceUl: value.balance == null ? "" : String(value.balance),
    wallet: value.wallet || "",
    parentId: parent == null || parent === "" ? null : String(parent),
    rootId: value.root_id == null || value.root_id === "" ? String(id) : String(value.root_id),
    sampleType: value.sample_type || "",
    createdBy: value.created_by || "",
    destroyed: Boolean(value.destroyed),
  };
}

export function resolveLookup(lookup, codeIndex, tokens) {
  if (!lookup || lookup.kind === "empty") return { status: "empty" };
  if (lookup.kind === "unknown") return { status: "invalid", raw: lookup.raw };
  if (lookup.kind === "code") {
    const id = codeIndex.get(lookup.code);
    if (id == null) return { status: "missing", code: lookup.code };
    const tokenId = String(id);
    if (!tokens.has(tokenId)) return { status: "missing", code: lookup.code, tokenId };
    return { status: "token", tokenId, code: lookup.code };
  }
  const tokenId = String(lookup.tokenId);
  if (!tokens.has(tokenId)) return { status: "missing", tokenId };
  return { status: "token", tokenId };
}

export function viewToken(tokenId, indexes) {
  const tokens = indexes.tokens;
  const raw = tokens.get(String(tokenId));
  if (!raw) return null;
  const token = asToken(tokenId, raw);
  const parents = [];
  const seen = new Set([token.id]);
  let cursor = token.parentId;
  while (cursor && !seen.has(cursor)) {
    seen.add(cursor);
    const row = tokens.get(cursor);
    if (!row) break;
    const parent = asToken(cursor, row);
    parents.push(parent);
    cursor = parent.parentId;
  }
  const children = [];
  for (const [id, row] of tokens) {
    if (row && row.parent_id != null && String(row.parent_id) === token.id) {
      children.push(asToken(id, row));
    }
  }
  children.sort((a, b) => Number(a.id) - Number(b.id));
  const rootRow = tokens.get(token.rootId);
  const rootCode = (rootRow && rootRow.code) || token.code;
  return {
    token,
    wallet: describeWallet(token.wallet, indexes.wallets),
    parents,
    children,
    rootCode,
    datasets: datasetsFor(token, parents, indexes.attachments),
    timeline: timelineFor(token, rootCode, indexes.events, indexes.transactions, indexes.wallets, indexes.explorer),
  };
}

export function datasetsFor(token, parents, attachments) {
  const own = attachmentList(token.id, attachments).map((item) =>
    asDataset(item, { inherited: false, id: token.id, code: token.code }),
  );
  const inherited = [];
  for (const ancestor of parents) {
    for (const item of attachmentList(ancestor.id, attachments)) {
      inherited.push(asDataset(item, { inherited: true, id: ancestor.id, code: ancestor.code }));
    }
  }
  return { own, inherited };
}

function attachmentList(tokenId, attachments) {
  const value = attachments.get(String(tokenId));
  return Array.isArray(value) ? value : [];
}

function asDataset(item, from) {
  return {
    uri: item.data_uri || "",
    type: item.data_type || "",
    step: item.step || "",
    sha256: item.content_hash || "",
    licence: item.licence || "",
    inherited: from.inherited,
    fromId: from.id,
    fromCode: from.code,
  };
}

export function timelineFor(token, rootCode, events, transactions, wallets, explorer) {
  const rows = [];
  for (const event of events || []) {
    if (!eventTouches(event, token, rootCode)) continue;
    const tx = transactions.get(String(event.transactionId));
    const hash = tx && tx.hash ? String(tx.hash) : "";
    rows.push({
      id: event.id,
      tag: event.tag,
      label: EVENT_LABELS[event.tag] || event.tag,
      timestamp: event.timestamp,
      summary: summarizeEvent(event, wallets),
      hash,
      explorer: hash && explorer ? `${String(explorer).replace(/\/$/, "")}/${hash}` : "",
    });
  }
  rows.sort((a, b) => String(a.timestamp).localeCompare(String(b.timestamp)) || a.id - b.id);
  return rows;
}

export function eventTouches(event, token, rootCode) {
  const payload = (event && event.payload) || {};
  if (payload.token_id != null && String(payload.token_id) === token.id) return true;
  if (payload.code != null && payload.code === token.code) return true;
  if (LINEAGE_TAGS.has(event.tag) && payload.root != null && payload.root === rootCode) return true;
  return false;
}

export function summarizeEvent(event, wallets) {
  const payload = event.payload || {};
  const parts = [];
  if (payload.reason) parts.push(String(payload.reason).replaceAll("-", " "));
  if (payload.outcome) parts.push(String(payload.outcome).replaceAll("_", " "));
  if (payload.volume != null) parts.push(`${payload.volume} µL`);
  if (payload.amount != null) parts.push(`${payload.amount} µL`);
  if (payload.burned != null) parts.push(`burned ${payload.burned} µL`);
  if (payload.balance != null) parts.push(`balance ${payload.balance} µL`);
  if (payload.to_) parts.push(`to ${walletName(payload.to_, wallets)}`);
  if (payload.parent && event.tag === "MINT") parts.push(`from ${payload.parent}`);
  if (event.tag === "DATA_ATTACHED") {
    if (payload.data_type) parts.push(payload.data_type);
    if (payload.step) parts.push(payload.step);
  }
  if (payload.request_id != null && (event.tag === "ACCESS_REQUEST" || event.tag === "ACCESS_APPROVED")) {
    parts.push(`request ${payload.request_id}`);
  }
  return parts.join(" · ");
}

function walletName(address, wallets) {
  const row = wallets && wallets.get(address);
  return (row && row.label) || shortAddress(address);
}

export function formatTimestamp(iso, options = {}) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return String(iso || "");
  return new Intl.DateTimeFormat(options.locale || undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: options.timeZone,
    hourCycle: "h23",
  }).format(date);
}

export function safeHttpUrl(value) {
  try {
    const url = new URL(String(value));
    if (url.protocol === "https:" || url.protocol === "http:" || url.protocol === "ipfs:") return url.href;
  } catch {
    return "";
  }
  return "";
}

export function loadIndexes(fixture) {
  return {
    codeIndex: indexRows(fixture.codeIndex),
    tokens: indexRows(fixture.tokens),
    wallets: indexRows(fixture.wallets),
    attachments: indexRows(fixture.attachments),
    transactions: indexTransactions(fixture.transactions),
    events: fixture.events || [],
    explorer: fixture.explorer || "",
  };
}
