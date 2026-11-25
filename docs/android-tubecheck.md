---
layout: default
title: Android Tube Check
---

# Android Tube Check

The Android prototype lives in [`apps/android-tubecheck/`](../apps/android-tubecheck/README.md). **Verify** is a native read of the public TzKT index, using the same per-tube mapping as the [phone viewer](viewer.md). **Ship and receive** talk to a thin, Shadownet-only HTTP front over the Python [bridge](../bridge/README.md) when a service URL and bearer token are entered in Settings. Without those settings the tabs stay a labelled preview. The supported phone viewer remains the static page in [`app/`](../app/README.md).

## Signing HTTP front

Staff custody should not put a private key, mnemonic or Tezos wallet in the phone. Signing stays on a machine that already holds testnet octez aliases. The service is a thin HTTP layer, not a new on-chain API and not a replacement for the contract entrypoints. `TezosBackend.submit` in the bridge still refuses injection; this front is a separate, Shadownet-only path.

Run it from the bridge package with a config file that lives **outside the git tree**:

```bash
export PYTHONPATH=src
python3 -m bioid_bridge.signing_http --config /path/to/service.json
```

The service binds to `127.0.0.1` by default (port 8787). It checks the RPC chain id on every signing path and refuses any network other than Shadownet (`NetXsqzbfFenSTS`). Bearer tokens and octez keys are not in this repository.

### Routes

Staff present a bearer token. A later version can replace that with the institution's ordinary account (OIDC). The app holds only the token, never a chain key.

| Method | Path | Result |
|---|---|---|
| `GET` | `/health` | Network, contract and chain id (no auth) |
| `GET` | `/me` | Staff name, org, their wallets, and ship/receive destinations |
| `GET` | `/custody/inbound` | Tubes currently in a `TRANSIT` wallet |
| `POST` | `/custody/ship/preflight` | Simulate `ship` |
| `POST` | `/custody/receive/preflight` | Simulate `receive` |
| `POST` | `/custody/ship` | Sign and inject `ship(code, to_wallet, data)` |
| `POST` | `/custody/receive` | Sign and inject `receive(code, to_wallet, data)` |

Ship and receive bodies are JSON: `client_request_id`, `tube_code`, `to_wallet`, and optionally `token_id` and `registered_via` (off-chain only). A successful inject returns `200` with `{ "op_hash" }`. A rule problem returns `202` with `{ "reasons" }` and writes nothing. The same `client_request_id` with the same body returns the stored hash; the same id with a different body returns `409`.

On-chain rules are unchanged. The destination of `ship` must be a `TRANSIT` wallet. The contract has no ship `reason` parameter; it always records `shipped`. `receive` destinations are `STORAGE`, `INTAKE` or `QUARANTINE` (or `EXTERNAL_USER` only with an approved access request). Inbound tubes are those sitting in a transit wallet, derived from the contract, not from a second invented index.

The current Shadownet custody prototype (synthetic data) is recorded in [`pilot/deployments/shadownet-custody.json`](../pilot/deployments/shadownet-custody.json). The earlier public demo contract is unchanged.

A physical phone cannot reach `127.0.0.1` on the machine that runs the service. Reachability needs a path the operator approves (SSH tunnel, VPN, or a temporary public tunnel). Do not open a public tunnel by default.
