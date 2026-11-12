import { DEFAULT_NETWORK, NETWORKS, TIP, networkById } from "../config.js";
import {
  formatTimestamp,
  humanStatus,
  loadIndexes,
  lookupFromQuery,
  parseScan,
  resolveLookup,
  safeHttpUrl,
  shortAddress,
  viewToken,
} from "./parse.js";
import { cameraErrorText, startScan } from "./scan.js";
import { loadContract } from "./tzkt.js";

const app = document.querySelector("#app");
const cache = new Map();
let scanStop = null;

const state = {
  networkId: networkFromLocation(),
  loading: false,
  error: "",
  data: null,
};

window.addEventListener("popstate", () => {
  state.networkId = networkFromLocation();
  render();
  ensureData();
});

render();
ensureData();

function networkFromLocation() {
  const requested = new URLSearchParams(location.search).get("network");
  return NETWORKS[requested] ? requested : DEFAULT_NETWORK;
}

function currentLookup() {
  return lookupFromQuery(new URLSearchParams(location.search));
}

async function ensureData() {
  const network = networkById(state.networkId);
  state.error = "";
  if (!network.contract) {
    state.data = null;
    state.loading = false;
    render();
    return;
  }
  if (cache.has(network.id)) {
    state.data = cache.get(network.id);
    state.loading = false;
    render();
    return;
  }
  state.loading = true;
  state.data = null;
  render();
  try {
    const raw = await loadContract(network);
    const indexes = loadIndexes({
      codeIndex: raw.codeIndex,
      tokens: raw.tokens,
      wallets: raw.wallets,
      attachments: raw.attachments,
      transactions: raw.transactions.map((row) => ({
        id: row.id,
        hash: row.hash,
        timestamp: row.timestamp,
      })),
      events: raw.events,
      explorer: network.explorer,
    });
    cache.set(network.id, indexes);
    state.data = indexes;
    state.error = "";
  } catch (error) {
    state.error = error.message || "The indexer could not be read.";
  } finally {
    state.loading = false;
    render();
  }
}

function render() {
  const network = networkById(state.networkId);
  app.replaceChildren();
  app.append(header(network), main(network), footer());
}

function header(network) {
  const banner = network.demo
    ? "Shadownet testnet demo, synthetic data"
    : "Mainnet is read-only. No contract is configured, so nothing is fetched.";
  return el("header", { class: "top" }, [
    el("p", { class: "wordmark" }, [el("span", { text: "BioID" }), " tube viewer"]),
    el("p", { class: network.demo ? "banner" : "banner quiet", role: "status", text: banner }),
    networkSelect(network),
  ]);
}

function networkSelect(network) {
  const select = el("select", { id: "network", "aria-label": "Network" });
  for (const item of Object.values(NETWORKS)) {
    const option = el("option", { value: item.id, text: item.label });
    if (item.id === network.id) option.selected = true;
    select.append(option);
  }
  select.addEventListener("change", () => {
    const url = new URL(location.href);
    if (select.value === DEFAULT_NETWORK) url.searchParams.delete("network");
    else url.searchParams.set("network", select.value);
    history.pushState({}, "", url);
    state.networkId = select.value;
    ensureData();
  });
  return el("label", { class: "network" }, ["Network ", select]);
}

function main(network) {
  const body = el("main", {});
  body.append(searchForm());
  if (state.loading) {
    body.append(el("p", { class: "status", text: "Reading the contract from TzKT…" }));
    return body;
  }
  if (state.error) {
    body.append(el("p", { class: "status error", role: "alert", text: state.error }));
    return body;
  }
  if (!network.contract) {
    body.append(
      el("p", { class: "status", text: "Set a contract address in app/config.js to read mainnet. The viewer never signs." }),
    );
    return body;
  }
  const indexes = state.data;
  if (!indexes) return body;
  const resolved = resolveLookup(currentLookup(), indexes.codeIndex, indexes.tokens);
  if (resolved.status === "empty") {
    body.append(intro(network), tubeList(indexes));
    return body;
  }
  if (resolved.status !== "token") {
    const who = resolved.code || resolved.tokenId || resolved.raw || "That value";
    body.append(
      el("p", {
        class: "status error",
        role: "alert",
        text: `${who} is not a tube on this contract.`,
      }),
    );
    return body;
  }
  const view = viewToken(resolved.tokenId, indexes);
  if (!view) {
    body.append(el("p", { class: "status error", role: "alert", text: "That token is not on this contract." }));
    return body;
  }
  body.append(tokenCard(view, network), timelineCard(view), lineageCard(view), datasetCard(view));
  return body;
}

function searchForm() {
  const input = el("input", {
    id: "lookup",
    name: "lookup",
    type: "text",
    autocomplete: "off",
    autocapitalize: "characters",
    placeholder: "SY00000221 or token id",
    "aria-label": "Tube code or token id",
  });
  const lookup = currentLookup();
  if (lookup.kind === "code") input.value = lookup.code;
  else if (lookup.kind === "token") input.value = lookup.tokenId;
  const form = el("form", { class: "search", action: "" }, [
    input,
    el("button", { type: "submit", text: "Show" }),
    el("button", { type: "button", id: "scan-open", text: "Scan" }),
  ]);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    applyScan(input.value);
  });
  form.querySelector("#scan-open").addEventListener("click", openScan);
  return form;
}

function intro(network) {
  return el("section", { class: "card" }, [
    el("h1", { text: "Look up a tube" }),
    el("p", {
      text: "Scan the Data Matrix or QR on the tube, type its code, or open a link that already carries ?tube=.",
    }),
    el("p", { class: "meta", text: `Contract ${network.contract}` }),
    el("p", {}, [
      el("a", { href: `${network.explorer}/${network.contract}`, text: "View the contract on TzKT" }),
    ]),
  ]);
}

function tubeList(indexes) {
  const items = [...indexes.codeIndex.entries()]
    .map(([code, id]) => ({ code, id: String(id) }))
    .sort((a, b) => a.code.localeCompare(b.code));
  const list = el("ul", { class: "tubes" });
  for (const item of items) {
    const token = indexes.tokens.get(item.id);
    const volume = token && token.balance != null ? `${token.balance} µL` : "";
    const button = el("button", { type: "button" }, [
      el("span", { class: "code", text: item.code }),
      el("span", { class: "meta", text: volume }),
    ]);
    button.addEventListener("click", () => showCode(item.code));
    list.append(el("li", {}, [button]));
  }
  return el("section", { class: "card" }, [el("h2", { text: "Tubes on this contract" }), list]);
}

function tokenCard(view, network) {
  const { token, wallet } = view;
  const place = [wallet.site, wallet.process].filter(Boolean).join(" · ");
  return el("section", { class: "card token" }, [
    el("p", { class: "kicker", text: `Token ${token.id}` }),
    el("h1", { text: token.code }),
    el("p", { class: "volume", text: `${token.balanceUl} µL` }),
    el("p", { class: "status-line", text: humanStatus(token.status) }),
    el("dl", { class: "facts" }, [
      fact("Sample", token.sampleType),
      fact("Wallet", wallet.label),
      fact("Wallet type", wallet.type || "Unregistered"),
      fact("Where", place),
      fact("Address", wallet.address ? shortAddress(wallet.address) : ""),
    ]),
    wallet.address
      ? el("p", {}, [el("a", { href: `${network.explorer}/${wallet.address}`, text: "Wallet on TzKT" })])
      : null,
  ]);
}

function timelineCard(view) {
  const list = el("ol", { class: "timeline" });
  for (const event of view.timeline) {
    const when = formatTimestamp(event.timestamp);
    const head = el("div", { class: "when" }, [
      el("time", { datetime: event.timestamp || "", text: when }),
      el("strong", { text: event.label }),
    ]);
    const item = el("li", {}, [head]);
    if (event.summary) item.append(el("p", { text: event.summary }));
    if (event.explorer) {
      item.append(el("p", {}, [el("a", { href: event.explorer, text: "Operation on TzKT" })]));
    }
    list.append(item);
  }
  const body = [el("h2", { text: "Timeline" })];
  if (!view.timeline.length) body.push(el("p", { text: "No events for this tube." }));
  else {
    body.push(el("p", { class: "meta", text: "Times are shown in this phone’s local timezone." }));
    body.push(list);
  }
  return el("section", { class: "card" }, body);
}

function lineageCard(view) {
  const list = el("div", { class: "lineage" });
  const rootFirst = [...view.parents].reverse();
  for (const parent of rootFirst) list.append(lineageButton(parent, "Ancestor"));
  list.append(lineageButton(view.token, "This tube", true));
  for (const child of view.children) list.append(lineageButton(child, "Child"));
  return el("section", { class: "card" }, [
    el("h2", { text: "Lineage" }),
    el("p", { class: "meta", text: "Parents sit above this tube. Children sit below. Tap one to open it." }),
    list,
  ]);
}

function lineageButton(token, role, current = false) {
  const label = `${token.code} · ${token.sampleType || "tube"} · ${token.balanceUl} µL`;
  if (current) {
    return el("p", { class: "node self" }, [el("span", { class: "role", text: role }), el("span", { text: label })]);
  }
  const button = el("button", { type: "button", class: "node" }, [
    el("span", { class: "role", text: role }),
    el("span", { text: label }),
  ]);
  button.addEventListener("click", () => showCode(token.code));
  return button;
}

function datasetCard(view) {
  const blocks = [el("h2", { text: "Datasets" })];
  if (!view.datasets.own.length && !view.datasets.inherited.length) {
    blocks.push(el("p", { text: "No datasets on this tube or its ancestors." }));
    return el("section", { class: "card" }, blocks);
  }
  if (view.datasets.own.length) {
    blocks.push(el("h3", { text: "Attached to this tube" }));
    blocks.push(datasetList(view.datasets.own));
  }
  if (view.datasets.inherited.length) {
    blocks.push(el("h3", { text: "Inherited from ancestors" }));
    blocks.push(datasetList(view.datasets.inherited));
  }
  return el("section", { class: "card" }, blocks);
}

function datasetList(rows) {
  const list = el("ul", { class: "datasets" });
  for (const row of rows) {
    const href = safeHttpUrl(row.uri);
    const uri = href ? el("a", { href, text: row.uri }) : el("span", { text: row.uri });
    const item = el("li", {}, [
      el("p", {}, [uri]),
      el("p", { text: `Type ${row.type} · step ${row.step}` }),
      el("p", { class: "hash", text: `sha256 ${row.sha256}` }),
    ]);
    if (row.inherited) {
      item.append(el("p", { class: "inherited", text: `Inherited from ${row.fromCode}` }));
    }
    list.append(item);
  }
  return list;
}

function footer() {
  return el("footer", {}, [
    el("p", {}, ["Tips in tez: ", el("a", { href: TIP.url, text: TIP.name })]),
    el("p", {}, [el("a", { href: "labels.html", text: "Print tube labels" })]),
    el("p", { class: "meta", text: "Read only. No keys, no signing, no personal data." }),
  ]);
}

function fact(name, value) {
  if (!value) return null;
  return el("div", {}, [el("dt", { text: name }), el("dd", { text: value })]);
}

function showCode(code) {
  const url = new URL(location.href);
  url.searchParams.set("tube", code);
  url.searchParams.delete("token");
  history.pushState({}, "", url);
  render();
}

function applyScan(raw) {
  const parsed = parseScan(raw);
  const url = new URL(location.href);
  url.searchParams.delete("tube");
  url.searchParams.delete("token");
  if (parsed.kind === "code") url.searchParams.set("tube", parsed.code);
  else if (parsed.kind === "token") url.searchParams.set("token", parsed.tokenId);
  else if (parsed.kind === "unknown") url.searchParams.set("tube", parsed.raw);
  history.pushState({}, "", url);
  render();
  const field = document.querySelector("#lookup");
  if (field) field.focus();
}

async function openScan() {
  closeScan();
  const dialog = el("dialog", { id: "scanner" }, [
    el("p", { id: "scan-status", text: "Starting the camera…" }),
    el("video", { id: "scan-video", autoplay: "autoplay", muted: "muted", playsinline: "playsinline" }),
    el("button", { type: "button", id: "scan-close", text: "Close" }),
  ]);
  document.body.append(dialog);
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
  dialog.querySelector("#scan-close").addEventListener("click", closeScan);
  dialog.addEventListener("cancel", (event) => {
    event.preventDefault();
    closeScan();
  });
  const video = dialog.querySelector("#scan-video");
  const status = dialog.querySelector("#scan-status");
  try {
    scanStop = await startScan({
      video,
      onStatus: (message) => {
        status.textContent = message;
      },
      onText: (text) => {
        closeScan();
        applyScan(text);
      },
    });
  } catch (error) {
    status.textContent = cameraErrorText(error);
  }
}

function closeScan() {
  if (scanStop) {
    try {
      scanStop();
    } catch {
      // The camera may already have stopped.
    }
    scanStop = null;
  }
  const dialog = document.querySelector("#scanner");
  if (!dialog) return;
  if (typeof dialog.close === "function" && dialog.open) dialog.close();
  dialog.remove();
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value);
  }
  for (const child of children) {
    if (child == null) continue;
    node.append(child);
  }
  return node;
}
