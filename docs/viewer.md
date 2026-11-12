---
layout: default
title: Phone viewer
---

# Phone viewer

The phone viewer is a static page under [`app/`](../app/README.md). It reads the synthetic Shadownet demo through TzKT. It does not sign, and it stores no keys.

Open a tube by scanning its Data Matrix or QR code, by typing the tube code or token id, or by following a link such as `?tube=SY00000221`. The page shows the current wallet, the volume in µL, the custody timeline, parents and children, and datasets, including those inherited from ancestor tubes.

The default network is Shadownet. Mainnet is only a read-only slot in [`app/config.js`](../app/config.js), with no contract filled in.

## Hosting

`app/` is plain files with relative links, so it can live at a host root or in a subpath.

GitHub Pages on a private repository can require a paid plan. Leave Pages off until the repository is public, or serve `app/` from any static host, or pin the directory on IPFS. Publishing steps for the documentation site stay in the [repository README](../README.md#site-github-pages). Those steps are separate from this viewer.

The viewer footer links to `bioid.tez` on mainnet for voluntary tips.
