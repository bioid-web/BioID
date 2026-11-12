import test from "node:test";
import assert from "node:assert/strict";
import { loadBwip } from "../scripts/load-bwip.mjs";
import { modulesToPng } from "../scripts/png.mjs";

const bwipjs = loadBwip();

test("bwip writes a Data Matrix SVG and the PNG encoder writes a PNG", () => {
  const text = "https://example.org/bioid/app/?tube=SY00000221";
  const svg = bwipjs.toSVG({ bcid: "datamatrix", text, scale: 3, padding: 1 });
  assert.match(svg, /^<svg/);
  assert.match(svg, /<\/svg>\s*$/);
  const raw = bwipjs.raw({ bcid: "datamatrix", text, scale: 1, padding: 0 });
  const symbol = raw[0];
  const png = modulesToPng(symbol.pixs, symbol.pixx, symbol.pixy, { scale: 4, quiet: 1 });
  assert.equal(png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.ok(png.length > 80);
});
