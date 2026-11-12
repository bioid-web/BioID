// Printable Data Matrix labels for the synthetic pilot tubes.
// Encodes {base}?tube=CODE. Writes SVG, PNG, and an HTML sheet
// that the browser can print to PDF.
//
//   node scripts/labels.mjs --base https://example.org/bioid/app/ --out labels/out

import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PILOT_CODES } from "../config.js";
import { tubeUrl } from "../src/parse.js";
import { loadBwip } from "./load-bwip.mjs";
import { modulesToPng } from "./png.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(here, "..");
const bwipjs = loadBwip();

const args = process.argv.slice(2);
const base = valueOf(args, "--base") || "https://example.org/bioid/app/";
const requestedOut = valueOf(args, "--out");
const outDir = requestedOut ? path.resolve(requestedOut) : path.join(appRoot, "labels/out");

const codes = await loadCodes();
await mkdir(outDir, { recursive: true });

const cards = [];
for (const code of codes) {
  const text = tubeUrl(base, code);
  const svg = bwipjs.toSVG({
    bcid: "datamatrix",
    text,
    scale: 4,
    padding: 2,
  });
  const raw = bwipjs.raw({ bcid: "datamatrix", text, scale: 1, padding: 0 });
  const symbol = raw[0];
  const png = modulesToPng(symbol.pixs, symbol.pixx, symbol.pixy, { scale: 10, quiet: 2, dark: 1 });
  const stem = code.toLowerCase();
  await writeFile(path.join(outDir, `${stem}.svg`), svg);
  await writeFile(path.join(outDir, `${stem}.png`), png);
  cards.push({ code, text, svg });
}

await writeFile(path.join(outDir, "sheet.html"), sheetHtml(base, cards));
console.log(`Wrote ${cards.length} labels to ${outDir}`);

function valueOf(argv, flag) {
  const index = argv.indexOf(flag);
  if (index === -1) return "";
  return argv[index + 1] || "";
}

async function loadCodes() {
  try {
    const file = path.join(here, "../fixtures/shadownet/code_index.json");
    const rows = JSON.parse(await readFile(file, "utf8"));
    const codes = rows
      .filter((row) => row && row.active !== false)
      .map((row) => String(row.key))
      .sort();
    if (codes.length) return codes;
  } catch {
    // Fall through to the config list.
  }
  return [...PILOT_CODES];
}

function sheetHtml(baseUrl, items) {
  const body = items
    .map(
      (item) => `<article class="label">
        ${item.svg}
        <p class="code">${escapeHtml(item.code)}</p>
        <p class="url">${escapeHtml(item.text)}</p>
      </article>`,
    )
    .join("\n");
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>BioID tube labels</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1rem; color: #1c1915; }
    h1 { font-size: 1.1rem; }
    .note { font-size: 0.85rem; }
    .grid { display: flex; flex-wrap: wrap; gap: 0.75rem; }
    .label { width: 42mm; border: 1px dashed #bbb; padding: 2mm; text-align: center; break-inside: avoid; }
    .label svg { width: 28mm; height: 28mm; }
    .code { font-weight: 700; margin: 0.2rem 0 0; }
    .url { font-size: 0.65rem; word-break: break-all; margin: 0.15rem 0 0; }
    @media print { .note, h1 { display: none; } body { margin: 0; } }
  </style>
</head>
<body>
  <h1>BioID synthetic pilot labels</h1>
  <p class="note">Shadownet testnet demo, synthetic data. Base ${escapeHtml(baseUrl)}. Use the browser print dialog and choose Save as PDF.</p>
  <div class="grid">
    ${body}
  </div>
</body>
</html>
`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
