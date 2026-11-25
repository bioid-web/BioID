---
layout: default
title: Phone viewer
---

# Phone viewer

The phone viewer is a static page under [`app/`](../app/README.md). It reads the synthetic Shadownet demo through TzKT. It does not sign, and it stores no keys.

Open a tube by scanning its Data Matrix or QR code, by typing the tube code or token id, or by following a link such as `?tube=SY00000221`. The page shows the current wallet, the volume in µL, the custody timeline, parents and children, and datasets, including those inherited from ancestor tubes.

A single lookup reads only that tube: its row in the contract's `tokens` big map, its contract events, the operations that emitted them, and then its parents and children up to the 8-generation lineage limit. The status shown is the effective one. A tube whose root has been withdrawn shows as frozen or stopped even if its own row still says active. The work grows with the size of that lineage, not with the size of the contract. On the demo contract a deep lineage takes about 16 requests. The full contract is loaded only for browsing.

The default network is Shadownet. Mainnet is only a read-only slot in [`app/config.js`](../app/config.js), with no contract filled in.

A native Android prototype in [`apps/android-tubecheck/`](../apps/android-tubecheck/README.md) uses the same per-tube TzKT mapping for Verify. Ship and receive are labelled previews only. The static page in `app/` remains the supported phone viewer.


## Hosting

`app/` is plain files with relative links, so it can live at a host root or in a subpath.

GitHub Pages on a private repository can require a paid plan. Leave Pages off until the repository is public, or serve `app/` from any static host, or pin the directory on IPFS. Publishing steps for the documentation site stay in the [repository README](../README.md#site-github-pages). Those steps are separate from this viewer.

The viewer footer links to `bioid.tez` on mainnet for voluntary tips.
