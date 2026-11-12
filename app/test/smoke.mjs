// Headless smoke test against the live Shadownet indexer.
// Requires playwright and a Chromium build:
//   npm install --no-save playwright
//   npx playwright install chromium
//   node test/smoke.mjs

import { createServer } from "node:http";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const port = Number(process.env.PORT || 4173);

const types = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
};

const server = createServer(async (request, response) => {
  const url = new URL(request.url, `http://127.0.0.1:${port}`);
  const relative = decodeURIComponent(url.pathname).replace(/^\/+/, "") || "index.html";
  const file = path.join(root, relative);
  if (!file.startsWith(root)) {
    response.writeHead(403);
    response.end();
    return;
  }
  try {
    const body = await readFile(file);
    response.writeHead(200, { "content-type": types[path.extname(file)] || "application/octet-stream" });
    response.end(body);
  } catch {
    response.writeHead(404);
    response.end("not found");
  }
});

await new Promise((resolve) => server.listen(port, "127.0.0.1", resolve));

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  server.close();
  console.error("playwright is not installed. Run: npm install --no-save playwright && npx playwright install chromium");
  process.exit(1);
}

const browser = await chromium.launch({
  timeout: 30000,
  headless: true,
  args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
});
const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
page.setDefaultTimeout(20000);
const base = `http://127.0.0.1:${port}/`;
const shots = process.env.SCREENSHOT_DIR || path.resolve(root, "../screenshots");
await mkdir(shots, { recursive: true });

try {
  await page.goto(`${base}index.html?tube=SY00000221`, { waitUntil: "networkidle" });
  await page.getByText("Shadownet testnet demo, synthetic data").waitFor();
  await page.getByRole("heading", { name: "SY00000221" }).waitFor();
  await page.locator(".volume").getByText("600 µL", { exact: true }).waitFor();
  await page.locator("dd").getByText("SYN-PILOT-EXT", { exact: true }).waitFor();
  await page.locator("dd").getByText("EXTERNAL_USER", { exact: true }).waitFor();
  await page.getByRole("link", { name: "Operation on TzKT" }).first().waitFor();
  await page.screenshot({ path: path.join(shots, "tube-221.png"), fullPage: true });

  await page.getByRole("button", { name: /SY00000202/ }).click();
  await page.getByRole("heading", { name: "SY00000202" }).waitFor();
  await page.locator(".volume").getByText("0 µL", { exact: true }).waitFor();
  await page.screenshot({ path: path.join(shots, "lineage-parent.png"), fullPage: true });

  await page.goto(`${base}index.html?token=8`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "SY00000241" }).waitFor();
  await page.getByText("Inherited from ancestors").waitFor();
  await page.getByText("Inherited from SY00000212").waitFor();
  await page.screenshot({ path: path.join(shots, "tube-241-inherited.png"), fullPage: true });

  await page.goto(`${base}index.html`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "Look up a tube" }).waitFor();
  await page.getByRole("button", { name: /SY00000211/ }).waitFor();
  await page.screenshot({ path: path.join(shots, "home.png"), fullPage: true });

  await page.locator("#network").selectOption("mainnet");
  await page.getByText("No contract is configured, so nothing is fetched.").waitFor();
  await page.screenshot({ path: path.join(shots, "mainnet-empty.png"), fullPage: true });
  await page.locator("#network").selectOption("shadownet");
  await page.getByRole("heading", { name: "Look up a tube" }).waitFor();

  await page.getByLabel("Tube code or token id").fill("SY00000999");
  await page.getByRole("button", { name: "Show" }).click();
  await page.getByRole("alert").waitFor();
  await page.getByText("SY00000999 is not a tube on this contract.").waitFor();
  await page.screenshot({ path: path.join(shots, "missing-code.png"), fullPage: true });

  await page.getByRole("button", { name: "Scan" }).click();
  await page.locator("#scan-status").waitFor();
  const scanText = await page.locator("#scan-status").innerText();
  if (!scanText) throw new Error("scan dialog did not report a status");
  await page.screenshot({ path: path.join(shots, "scan-dialog.png") });
  await page.getByRole("button", { name: "Close" }).click();

  await page.goto(`${base}labels.html`, { waitUntil: "networkidle" });
  await page.locator("#grid canvas").first().waitFor();
  await page.locator(".code").getByText("SY00000221", { exact: true }).waitFor();
  await page.screenshot({ path: path.join(shots, "labels.png"), fullPage: true });
  console.log("smoke ok");
} finally {
  await browser.close();
  server.close();
}
