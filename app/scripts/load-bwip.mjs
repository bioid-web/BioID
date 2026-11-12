// The browser build is a UMD file. This package is "type": "module", so a
// plain import would run that file as ESM, where `module` and `this` are
// both unset. Compile it as a CommonJS module instead.
import { readFileSync } from "node:fs";
import { Module } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

export function loadBwip() {
  const file = path.join(path.dirname(fileURLToPath(import.meta.url)), "../vendor/bwip-js-min.js");
  const compiled = new Module(file);
  compiled.filename = file;
  compiled.paths = Module._nodeModulePaths(path.dirname(file));
  compiled._compile(readFileSync(file, "utf8"), file);
  return compiled.exports;
}
