# Phone viewer

A static, read-only page for a phone. It scans a tube's Data Matrix or QR code, or takes a typed code, a token id, or a link such as `?tube=SY00000221`, then reads that tube from the public TzKT index.

It shows the holding wallet's label and type, the volume in µL, a timeline of custody events in local time with a link to each operation, the parent and child tubes, and datasets attached to the tube or inherited from its ancestors. The Shadownet build says **Shadownet testnet demo, synthetic data**.

Nothing here signs a transaction. There is no backend and no key.

## Run it

Any static file server whose root is this `app/` directory:

```bash
python3 -m http.server 4173
```

Open `http://127.0.0.1:4173/`. Paths are relative, so the same files work at a host root or under a prefix such as `/bioid/app/`.

Deep link: `index.html?tube=SY00000221`. A printed symbol should encode an absolute URL with that query. `?token=8` opens a token id directly.

## Network

[`config.js`](config.js) is the only network file. Shadownet is the default, pointed at `https://api.shadownet.tzkt.io/v1` and contract `KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix`. That API base was checked on 19 October 2026: `GET /v1/head` returned chain `shadownet`, chain id `NetXsqzbfFenSTS`.

Mainnet is a second entry in the same file. Its contract address is empty, the page is read-only, and it does not call mainnet until you fill that address yourself. Do not put a key in this file.

Wallet labels come from the on-chain wallet registry. The deployment record in [`pilot/deployments/shadownet.json`](../pilot/deployments/shadownet.json) describes the same synthetic wallets.

## Scanner

Where the browser supports it, the page uses the Data Matrix and QR formats of the [Barcode Detection API](https://developer.mozilla.org/en-US/docs/Web/API/Barcode_Detection_API). Otherwise it loads the vendored `@zxing/browser` 0.1.5 build in [`vendor/zxing-browser.js`](vendor/zxing-browser.js), which reads both symbologies. The camera needs HTTPS, or localhost.

## Labels

[`labels.html`](labels.html) draws a Data Matrix for every pilot tube with [`vendor/bwip-js-min.js`](vendor/bwip-js-min.js) (bwip-js 4.7.0). The base URL field defaults to this app's directory. Each symbol encodes `{base}?tube=CODE`. Download PNG or SVG from the page, or print the sheet and choose Save as PDF.

The same files can be written without a browser:

```bash
node scripts/labels.mjs --base https://example.org/bioid/app/ --out labels/out
```

That writes one SVG, one PNG, and `sheet.html` per run. Open `sheet.html` and print to PDF. The default base is a placeholder; set it to the URL where you actually host `app/`.

## Hosting

The page is a directory of files. It does not need a build.

GitHub Pages on a **private** repository can require a paid plan. This recipe does not turn Pages on and does not change who can see the repository. When you want the viewer on the public web, pick one of these:

- Make the repository public, then enable Pages (the docs site already describes publishing `/docs`; the viewer is a separate static directory, so publish `app/` with any Pages source that can serve it, or copy `app/` to the site).
- Put `app/` on any static host: a bucket, a small VM, or the same host as the docs.
- Add the directory to IPFS and share the CID. Relative links keep working. The TzKT calls are absolute and need a network.

Serve `index.html` for the directory URL if your printed codes use `https://host/app/?tube=…`. Codes can also point straight at `index.html?tube=…`.

The footer keeps the mainnet tip link for [`bioid.tez`](https://tzkt.io/tz1Tm5drMq3zueTpSonJ2FE7P3MBZN9RBNta). Tips are not part of the testnet demo.

## Tests

Parser and lineage tests use the recorded TzKT fixtures in [`fixtures/shadownet/`](fixtures/shadownet/README.md). They do not touch the network.

```bash
node --test test/parse.test.mjs test/labels.test.mjs
```

A headless browser smoke test loads the page and reads the live Shadownet contract:

```bash
npm install --no-save playwright
npx playwright install chromium
node test/smoke.mjs
```

Set `SCREENSHOT_DIR` to choose where the smoke test writes PNG files. It needs outbound access to `api.shadownet.tzkt.io`.
