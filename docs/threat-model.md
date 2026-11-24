---
title: Threat model
---

# Threat model

Version 0.4, 24 November 2026. This page backs section 3.9 of the white paper. The status column says whether a measure is **implemented** in this repository, **proposed** (a tested contract patch in `contracts/proposals/` that is not originated anywhere yet), or **planned**.

## What the record proves, and what it does not

A public chain proves that a record was made, by which key, when, and in what order, and that nobody changed it afterwards. It does not prove that a tube is in a freezer, that the right liquid is in the tube, or that the person behind a key is who they claim to be. Every guarantee below follows from that.

## Assets

1. The custody, volume and lineage history of each tube.
2. The withdrawal state of each lineage, and the evidence that destruction happened.
3. The link from a tube to a donor. **It is never on-chain.** It sits in the biobank's own records.
4. Off-chain documents referenced by fingerprint: metadata, datasets and access agreements.
5. Keys: station custodians, the admin (registry) key, and the withdrawal-owner role.

## Actors

Custodians at stations and sites, couriers, external users with approved access, the registry admin, the institutional withdrawal owner, auditors and the public, and attackers. An attacker may be an outsider or a participant acting dishonestly.

## Threats and measures

| # | Threat | Measure | Status | What is left |
|---|---|---|---|---|
| T1 | Silent editing, deletion or back-dating of history | Public append-only chain; corrections are new linked records | implemented | None for on-chain data. Off-chain copies must be checked against fingerprints. |
| T2 | Volume appearing from nowhere through transformation records | Burn never exceeds balance. Plain aliquots and splits are capped by the burn. Isolation, elution, dilution and titration record the added volume (or dilution factor) and are capped by burn plus added. Only `measured` may raise a volume. | bridge implemented; contract proposed | An isolation without a recorded added volume is uncapped by design (the elution may legitimately be larger). Auditors should flag isolations with no added volume recorded. |
| T3 | A custodian records an event that did not happen, or leaves one out ("garbage in") | Typed wallets and an enforced transition matrix. Two-step ship and receive, so the receiving site confirms. Reconciliation against LIMS exports. Sampled physical audits against the public record. | implemented (bridge, contract, reconcile) | Collusion between sender and receiver. Physical audits remain necessary. |
| T4 | One key both orders and certifies a destruction | The owner orders with `withdraw`; only the custodian holding the tube can `confirm_destroyed` | bridge implemented; contract proposed | Owner and custodian at the same institution could still collude. Use separate staff and keys. |
| T5 | A withdrawal fails to reach a derived tube | The outcome is stored once on the root, and every operation on any descendant checks it, at constant cost wherever the tube sits | proposed (`v0.4-lifecycle.patch`); bridge implemented | Material outside the system, such as an unregistered tube, is invisible to any ledger. |
| T6 | A large lineage cannot be withdrawn because gas grows with its size | No loop: one write on the root. The per-lineage `by_root` set, which also grew with every child, is removed. | proposed | None known. Measure on a testnet before adoption. |
| T7 | A stop-use cannot later be made stricter | `stop_use` may be escalated once to `destroy` or `anonymise`, as a new visible event. Nothing can be relaxed. | proposed; bridge implemented | – |
| T8 | The withdrawal-owner key is lost, stolen, or its holder leaves | The owner set at mint is an institutional role held by a multisig contract (for example TzSafe 2-of-3: operator, institution backup, cold escrow). Signers are added, removed or replaced inside the multisig by its own threshold, so the owner address in BioID never changes. | design (deployment practice; no contract change needed) | A compromised owner threshold can withdraw (freeze) lineages, but cannot erase history or move custody. Moving the role to a different institution's address is not supported. A `rotate_owner` entrypoint was written and tested, then dropped to keep the contract under the 32 KB operation limit. Losing all owner keys cannot be recovered on-chain, by design. |
| T9 | A stolen station or custodian key | HSM or KMS key references only (the bridge refuses raw secrets). The admin deactivates the wallet with `set_wallet_active`. Every action stays attributable. | implemented | Misuse until deactivation. Monitor for unusual activity. |
| T10 | Lineage views silently stop at 8 generations | `transform` refuses a ninth generation (`BIOID_DEPTH`), so the views are complete by construction. The bridge applies the same rule. | proposed; bridge implemented | Very deep derivation chains need a larger limit in a future contract version. |
| T11 | Confirming a guess about a fingerprinted document | Salted fingerprints (HMAC-SHA256, salt kept off-chain) for guessable documents such as consent-form templates, short agreements and small CSVs. Plain SHA-256 for large public datasets. | implemented (`bioid-bridge fingerprint`) | Losing a salt makes the fingerprint unverifiable. Store salts as durably as the documents. |
| T12 | Linking tubes to people through timing, wallet reuse or activity patterns | No personal data on-chain; tube codes carry no personal meaning; rack batching blurs timing | partly implemented | Needs formal linkability analysis (white paper §7). |
| T13 | An indexer or RPC returns errors or wrong answers | The viewer retries transient errors with backoff and reads only one tube's rows. Checks should cross-read a second indexer or an RPC node. | retry and per-tube reads implemented; cross-check planned | – |
| T14 | Off-chain metadata disappears (lost pins, dead links) | Durability plan: two independent pinning services plus institutional copies, periodic re-verification, archives of chain data | planned ([durability.md](durability.md)) | Depends on people actually operating the plan. |
| T15 | The chain stops, or changes in a way that breaks the record | Tezos was chosen for continuity. Exports of storage and events are archived with checksums, so history can be checked without the live chain. | planned | Residual risk is inherent in any single chain. |
| T16 | Someone mistakes tokens for tradable assets | FA2 `transfer` is disabled. Custody moves only through typed entrypoints. No payment token. | implemented | Communication. |
| T17 | A requester's wallet is not the institution it claims to be | Access needs custodian or admin approval, and the agreement is fingerprinted | implemented | Planned: fingerprint a GA4GH Passport visa or a W3C Verifiable Credential in the request ([related work](related-work.md) §5). |
| T18 | Off-chain metadata or results on IPFS are read by people outside the data-sharing agreement (a SHA-256 fingerprint is a hash, not encryption) | Design: AES-256-GCM envelope encryption. Each object has its own data key, wrapped for each recipient named in the agreement. Only the SHA-256 of the ciphertext is anchored with `attach_data`. On withdrawal, all copies of the keys are destroyed (crypto-shredding). No contract change. | design (white paper §3.11) | Copies a partner has already decrypted cannot be recalled. Future cryptanalysis (including quantum) may weaken pinned ciphertext, so DNA data stays off public networks. Key destruction must be proven off-chain. |

## Out of scope

Physical security of freezers; the correctness of LIMS data before it reaches the bridge; legal compliance in any specific jurisdiction. For the last one, see the EDPB blockchain guidelines cited in [related work](related-work.md) §8. A DPIA is required before any real deployment.
