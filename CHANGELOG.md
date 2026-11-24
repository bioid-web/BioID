# Changelog

All notable changes to this repository. Code is MIT, documentation CC BY 4.0.

## v0.4 (draft, November 2026)

Work from the v0.4 improvement sprint, 23–24 November 2026. Every sample, tube code and wallet in the tests and examples is synthetic. Nothing here was deployed, and nothing touched mainnet. The deployed Shadownet contract (`contracts/bioid_fa2.py`) is unchanged. Contract changes are tested proposals in `contracts/proposals/`.

### Contract (proposals, tested in SmartPy 0.24.2, not originated)

- `v0.4-integrity.patch`:
  - Volume conservation by transformation type, with a new `transform` parameter `added_ul`. Aliquots and splits are capped by the volume burned. Extraction and isolation may add elution volume. Dilution and titration must record the volume they add.
  - `confirm_destroyed` is custodian-only.
  - `adjust_volume` emits the previous volume, and only `measured` can raise a volume.
  - `unfreeze_anonymised` runs once.
- `v0.4-lifecycle.patch` (applies on top of the integrity patch):
  - Constant-cost withdrawal: the outcome is written once, on the root, and every operation checks it. The `by_root` set is removed.
  - `stop_use` can be escalated to `destroy` or `anonymise`.
  - Anonymisation at constant cost.
  - An explicit 8-generation lineage limit (`BIOID_DEPTH`).
  - The `tube` view returns the effective status, outcome, depth and owner.
  - New scenario: `bioid_lifecycle`.
- Owner key rotation: the owner should be an institutional multisig (for example TzSafe). A `rotate_owner` entrypoint was written and tested, then removed to stay under the 32,768-byte operation limit. Sizes are in `contracts/proposals/README.md`. A Shadownet dry run (not injected) measured 32,612 signed bytes, 156 under the limit, with about 80.7k gas and 33,004 bytes of storage. Decided: a multisig owner without `rotate_owner`, and freeing spare bytes deferred to a later upgrade.

### Bridge

- Withdrawal path: `withdraw`, `confirm_destroyed` and `unfreeze_anonymised`, including escalation from `stop_use`. Frozen tubes refuse custody, volume and access operations.
- Volume rules by transformation type, with `added_uL` or `dilution_factor`. History records the reason, the volume burned and the volume added.
- Lineage depth limit of 8 generations.
- `TezosBackend` encodes the withdrawal entrypoints. `TEZOS_CONTRACT_VERSION=v0.4` adds `added_ul` to the `transform` encoding.
- New `fingerprint` command for salted fingerprints (HMAC-SHA256, salt kept off-chain).
- New `export-epcis` command: GS1 EPCIS 2.0 JSON-LD export of a tube's lineage. An optional test checks the output against the GS1 schema.
- History rows carry `occurred_at` and `recorded_at`.
- Mapping examples gain the withdrawal, dilution and titration event types.

### Viewer

- TzKT client with retry, backoff and timeout. Client errors (4xx) are not retried.
- Per-tube reads. A lookup loads only that tube and its lineage (8 generations), not the whole contract.
- Effective status derived from the root's withdrawal events.
- The timeline shows the added volume and the previous volume.

### Documentation

- White paper v0.4 draft (`docs/whitepaper/BioID-whitepaper-v0.4-draft.md`). The repository recipe is now the primary design, and the lean21 mainnet trial is reported as history, with its results kept.
- New: related work (`docs/related-work.md`), threat model (`docs/threat-model.md`), durability and pinning plan (`docs/durability.md`).
- New design, not implemented and needing no contract change: keeping metadata hidden (white paper §3.11, threat T18, durability keys section). SHA-256 is a hash, not encryption. Off-chain metadata is encrypted with AES-256-GCM envelope encryption, data keys are wrapped per recipient under each data-sharing agreement, only the SHA-256 of the ciphertext goes on-chain, and destroying the keys on withdrawal works as crypto-shredding. The limits are stated: copies already decrypted, and future cryptanalysis.
- Updated: contract, proposals, bridge, viewer and index pages.

### External review

An AI review by Claude (Anthropic), dated 23 November 2026, came with a patch. Every finding was checked against the code before it was used.

- **Kept:**
  - the bridge withdrawal path and the operable check
  - the `TezosBackend` withdrawal encoding
  - the viewer's TzKT retry logic
  - the extra mapping event types
  - `confirm_destroyed` custodian-only
  - the `adjust_volume` rules
  - the findings on withdrawal gas, owner rotation, stop-use escalation, whole-contract viewer reads, the silent 8-generation view limit, durability claims and salted fingerprints, which became the lifecycle work above
  - the related-work leads (Dwarna, demonstrated consent, de-bi, EPCIS 2.0), after checking each source
- **Modified:**
  - Volume conservation. The review exempted isolations without a ceiling and had no dilution or titration. The rule now caps plain aliquots and splits by the burn and records added liquid for the other steps.
  - The contract volume check, now with `added_ul`, compiled and tested.
  - Owner rotation, done through a multisig instead of an entrypoint.
  - The "new origination" note. The proposal stays a patch, it will be tested on a testnet first, and the mainnet trial contract is never re-originated.
- **Rejected:**
  - Committing the review document, because it was out of date after these changes.
  - Changing the README DOI, which is the concept DOI on purpose.
