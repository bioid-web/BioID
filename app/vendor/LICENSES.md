# Vendored libraries

Pinned copies, committed so the viewer and the label page work without a CDN or an install step.

| File | Package | Version | Licence |
|---|---|---|---|
| `zxing-browser.js` | `@zxing/browser` bundled with `@zxing/library` | browser 0.1.5, library 0.21.3 | MIT |
| `bwip-js-min.js` | `bwip-js` | 4.7.0 (2025-07-01) | MIT |

`zxing-browser.js` is an esbuild bundle of `BrowserMultiFormatReader` from `@zxing/browser@0.1.5`. It is the camera fallback when `BarcodeDetector` cannot read Data Matrix. `bwip-js-min.js` draws Data Matrix symbols for the label page and `scripts/labels.mjs`.
