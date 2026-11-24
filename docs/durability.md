---
title: Durability plan
---

# Durability plan

Version 0.4, 24 November 2026. **This is a plan, not a running service.** It says what must survive for a BioID record to stay checkable for decades, who keeps each part, and how often it is checked. An adopter assigns the roles to named teams before going live.

## What must survive

| Part | Where it lives | Why it matters | How it is kept |
|---|---|---|---|
| Contract code, storage and events | The Tezos chain | The record itself | Tezos nodes (independent bakers and archive nodes). Plus periodic exports, see below. |
| Contract metadata (TZIP-16) and token metadata (TZIP-21) | IPFS, addressed by CID | Readable names and descriptions | Pin on at least **two independent pinning services** and on **one institutional IPFS node**. A CID is a content address, so any copy verifies against it. |
| Datasets attached with `attach_data` | `https://` or `ipfs://` URIs, with a SHA-256 or salted fingerprint on-chain | Evidence behind each step | Institutional or community repositories with their own preservation policy. The fingerprint proves which version was meant. |
| Salts for salted fingerprints | Off-chain, next to each document | Without the salt, the fingerprint cannot be checked | Stored with the same durability as the document, with an escrow copy held by the data steward. Never on-chain. |
| Wallet registry metadata | `metadata_uri` per wallet | Readable station names | As for token metadata. |
| Viewer, bridge and contract source | This repository | Lets anyone re-read the record later | GitHub, plus an archive of the repository in Software Heritage ([how to archive](https://www.softwareheritage.org/how-to-archive-reference-code/)), plus versioned releases deposited with a DOI. |
| The off-chain link from tube to donor | The biobank's own systems | Needed to act on a withdrawal | Normal institutional safeguards. **Deliberately not durable beyond its legal purpose:** deleting it is how anonymisation works. |

## Encryption keys for hidden metadata (design)

If metadata is kept hidden with envelope encryption (white paper §3.11), the keys become part of what must survive, and also part of what must be destroyable.

- **Data keys** (one AES-256-GCM key per object) are kept only in wrapped form: one copy per recipient named in a data-sharing agreement, plus one for the institution's key service. Plain data keys are never stored.
- **Durability.** The institution's wrapped copy is backed up with the same care as the document. Losing every copy of a data key makes that object unreadable for good, even though its ciphertext and its on-chain hash survive.
- **Destruction.** On a withdrawal that requires it, every wrapped copy is destroyed and the destruction is logged in the key service (crypto-shredding). The ciphertext may stay pinned. The on-chain hash still shows that the object existed and was not changed.
- **Limits.** Copies a partner has already decrypted are outside the institution's control. Ciphertext kept for decades may be weakened by future cryptanalysis. Data that must stay secret that long, such as DNA sequence, is kept in institutional storage, not pinned on public IPFS.

## Chain-data exports

The chain is the source of truth, but readers today depend on indexers (TzKT) and RPC nodes run by third parties. Two measures reduce that dependence.

1. **Periodic export.** Each quarter, export the contract storage, all bigmap keys, and all contract events (TzKT API, or your own archive node). Write SHA-256 checksums and deposit the bundle in a long-term repository. The export lets anyone check history even if today's indexers disappear. Comparing two exports also shows that nothing in the past changed.
2. **Second source.** Verification scripts should be able to read from two indexers, or from one indexer and a Tezos RPC node, and compare the results.

## Verification schedule

| When | What | Who |
|---|---|---|
| Every release | Run the bridge, viewer and contract test suites | Maintainers |
| Monthly | Resolve a random sample of 5% of metadata CIDs and dataset URIs and re-check their fingerprints | Data steward |
| Quarterly | Chain-data export with checksums; compare with the previous export | Data steward |
| Yearly | Full re-verification of every CID and fingerprint; review the pinning contracts; test restoring from the export alone | Data steward and quality manager |
| On any incident | Re-pin from the institutional node; record a new, linked correction event if a URI moved | Custodian of the affected data |

## Roles

- **Data steward**: owns pinning, exports and verification, and keeps the escrow copy of the salts.
- **Custodians**: keep attached datasets reachable, or record their new location.
- **Maintainers**: keep the code archived and reproducible.
- **Withdrawal owner** (institutional multisig): no durability duty. Losing their keys does not endanger the record (see the [threat model](threat-model.md), T8).

## Limits

Nothing guarantees that a public chain runs forever. The claim BioID makes is narrower: as long as the chain, or an archived export of it, and the pinned metadata survive, anyone can check the record without trusting the institution that wrote it.
