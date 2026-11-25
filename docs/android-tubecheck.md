---
layout: default
title: Android Tube Check
---

# Android Tube Check

The Android prototype lives in [`apps/android-tubecheck/`](../apps/android-tubecheck/README.md). **Verify** is a native read of the public TzKT index, using the same per-tube mapping as the [phone viewer](viewer.md). **Ship and receive are not connected.** The supported phone viewer remains the static page in [`app/`](../app/README.md).

## Planned: a thin HTTP front over the bridge

This section is a design note for later work. There is no such service in the repository today, and the Android app does not call one.

Staff custody should not put a private key, mnemonic or Tezos wallet in the phone. Signing stays with the institution (an HSM, a KMS, or a multisig such as TzSafe), behind the existing Python [bridge](../bridge/README.md). The planned service is a thin HTTP layer on that bridge, not a new on-chain API and not a replacement for the contract entrypoints.

A later version could look like this:

- Staff sign in with the institution's ordinary account (OIDC). The app holds only a short-lived bearer token, never a chain key.
- The service already knows the staff member's site and the wallets in `wallet_registry` they may use.
- **Ship** maps to the contract entrypoint `ship(code, to_wallet, data)`. The destination must be a `TRANSIT` wallet. The contract has no ship `reason` parameter; it always records `shipped`. Any staff note or "registered via camera or scanner" field stays off-chain, or goes in `data` only if it is a hash and URI that follow the existing `attach_data` rules (no personal data).
- **Receive** maps to `receive(code, to_wallet, data)`. The destination may be `STORAGE`, `INTAKE` or `QUARANTINE` (or `EXTERNAL_USER` only with an approved access request).
- Every request carries a `client_request_id`. The bridge already treats a retry with the same id as the same request, so a tube cannot be shipped twice by accident.
- The service re-checks the wallet rules, simulates the operation, and either injects it, or places a rule-breaking request on the existing review queue and writes nothing to the chain.
- Inbound tubes for a site are those sitting in a transit wallet whose next receive is that site, derived from the contract and the wallet registry, not from a second invented index.

Until that service exists, the Android Ship and Receive tabs stay a labelled preview, and all custody writes continue to go through the bridge CLI on a testnet with synthetic tubes.
