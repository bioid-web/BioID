import { PILOT_CODES, networkById, DEFAULT_NETWORK } from "../config.js";
import { tubeUrl } from "./parse.js";
import { loadContract } from "./tzkt.js";

const grid = document.querySelector("#grid");
const baseInput = document.querySelector("#base");
const status = document.querySelector("#label-status");
baseInput.value = new URL("./", window.location.href).href;

document.querySelector("#label-form").addEventListener("submit", (event) => {
  event.preventDefault();
  draw().catch((error) => {
    status.textContent = error.message || "Could not draw the labels.";
  });
});
document.querySelector("#print").addEventListener("click", () => window.print());

draw().catch((error) => {
  status.textContent = error.message || "Could not draw the labels.";
});

async function codes() {
  const network = networkById(DEFAULT_NETWORK);
  try {
    const data = await loadContract(network);
    const found = data.codeIndex
      .filter((row) => row && row.active !== false)
      .map((row) => String(row.key))
      .sort();
    if (found.length) return found;
  } catch {
    status.textContent = "TzKT was unreachable. Showing the recorded pilot codes.";
  }
  return [...PILOT_CODES];
}

async function draw() {
  const base = baseInput.value.trim();
  let parsed;
  try {
    parsed = new URL(base);
  } catch {
    status.textContent = "Enter an absolute base URL, including https://.";
    return;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    status.textContent = "The base URL must be http or https.";
    return;
  }
  const list = await codes();
  grid.replaceChildren();
  for (const code of list) {
    const text = tubeUrl(base, code);
    const canvas = document.createElement("canvas");
    window.bwipjs.toCanvas(canvas, {
      bcid: "datamatrix",
      text,
      scale: 4,
      padding: 2,
    });
    const svg = window.bwipjs.toSVG({
      bcid: "datamatrix",
      text,
      scale: 4,
      padding: 2,
    });
    const card = document.createElement("article");
    card.className = "label";
    const heading = document.createElement("p");
    heading.className = "code";
    heading.textContent = code;
    const link = document.createElement("p");
    link.className = "url";
    link.textContent = text;
    const actions = document.createElement("p");
    actions.className = "actions";
    actions.append(downloadLink(`${code}.png`, canvas.toDataURL("image/png")), " ", downloadSvg(code, svg));
    card.append(canvas, heading, link, actions);
    grid.append(card);
  }
  if (!status.textContent) status.textContent = `${list.length} labels. Print this page to save a PDF.`;
  else if (!status.textContent.includes("unreachable")) {
    status.textContent = `${list.length} labels. Print this page to save a PDF.`;
  }
}

function downloadLink(name, href) {
  const link = document.createElement("a");
  link.href = href;
  link.download = name;
  link.textContent = "PNG";
  return link;
}

function downloadSvg(code, svg) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  link.download = `${code}.svg`;
  link.textContent = "SVG";
  return link;
}
