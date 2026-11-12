---
title: Core operating principles
---

# Core operating principles

These principles are the rules for any ecosystem that adopts the BioID recipe. They are how a biobank keeps the ledger honest while adapting the design to local practice.

The words MUST, MUST NOT and SHOULD are used as in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119). A fork that relaxes a MUST should say so in its own documentation, in public, next to the change.

Wallet types, the transition matrix and the registry format are specified in [Wallet types](wallet-types.md).

## 1. No personal or donor-linkable data on-chain

An ecosystem MUST NOT put personal or donor-linkable data on the chain. That includes names, dates of birth, holding numbers, coordinates, and any value that can be walked back to a person or to an animal's owner. A `consent_ref` MUST be an opaque random id. The mapping stays in the off-chain consent register, where it can be deleted.

The ledger is public and durable. Erasure of the link is crypto-shredding of that off-chain record, which only works if the chain never held the link.

## 2. The chain mirrors physical reality

The chain MUST follow the tube, and MUST NOT run ahead of it. A move, receive, transform or consume SHOULD be recorded promptly after it happens in the lab or on the road. Withdrawal MUST freeze the lineage first. A balance MUST NOT be burned for destruction until someone confirms that the physical tube has been destroyed.

A ledger that says a tube is gone, or that it sits in a freezer it has not reached, will be treated as the truth by the next reader. A late entry can be explained. An early one cannot.

## 3. Every holding wallet is registered and typed

Before an address can hold a tube, it MUST be registered and given a type from [Wallet types](wallet-types.md). An address with no registry row, an unknown type, or `active: false` on the inbound path MUST NOT hold a balance.

Type is what makes the transition rules enforceable. An untyped address is just a key, and a key is not a freezer.

## 4. Wallets should have readable names

A holding wallet SHOULD have a readable [Tezos Domains](https://tezos.domains/) name, such as `bios.example.tez`, and that name SHOULD be recorded in the wallet registry next to the address. When an ecosystem actually registers the name, it SHOULD resolve to the same address as the registry row.

A raw `tz1` string does not tell a custodian which freezer they are signing for. The name is a label for humans. The registry row and the on-chain record stay authoritative if a name is wrong or missing. Names in this repository, including anything under `example.tez`, are synthetic placeholders and are not registered.

## 5. Hand-over between sites is two-step

A custody change between sites MUST be two steps. The sender ships the tube into a `TRANSIT` wallet. Only the destination custodian MAY then receive it into one of their own wallets. A single transfer from one site's storage to another site's storage MUST be rejected.

One signature cannot prove that a delivery happened. The second signature is the receiver saying the tube is in their hands.

## 6. Transform and use happen only in a process wallet

Deriving a new tube, or using volume in an assay inside the lab, MUST happen only in a `PROCESS` wallet. Every child token MUST record its parent, so the lineage stays attached to the root sample. A transform, or a consume-for-use, in storage, on intake, in transit or in quarantine MUST be rejected. Use by an approved external recipient is `report_use` on an `EXTERNAL_USER` wallet, which is the same burn with a different signer, not a transform. A change of place for the same physical tube MUST be a move of that same token, and MUST NOT be recorded by minting or burning. A new container MUST be a new token, and the burn MUST be only the volume taken from the parent, which keeps whatever volume remains.

Volume and parentage change on the bench, not in the freezer and not in a courier bag. A tube that is lost, rejected on arrival, or destroyed after withdrawal is a different event: it is burned where it actually sits, with its own reason, so the balance does not outlive the material. Those reasons are listed in the wallet-type rulebook.

## 7. Reason codes come from a published vocabulary

Every move, receive, transform, consume and withdrawal burn MUST carry a reason code from a controlled vocabulary the ecosystem publishes. Free text MUST NOT be the only reason on an event.

Indexers and partner labs can reconcile `shipped` with a local SOP only when the code list is shared. The starter list is in [Wallet types](wallet-types.md). Mapping those codes onto a particular ontology is for each ecosystem; a shared ontology mapping is to be confirmed.

## 8. Owners' rights and withdrawal are honoured promptly

The owner's right to withdraw MUST be honoured promptly. A withdrawal MUST freeze the full lineage of the root sample, in every wallet those tubes currently occupy. While a tube is frozen, custodians MUST NOT move it, transform it, or consume it.

Aliquots and extracts are still that sample. Freezing only the primary tube would leave the derived tubes usable.

## 9. Each ecosystem publishes its own registry

Each ecosystem MUST publish its own wallet registry and MUST anchor it, for example with a [TZIP-16](https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-16/tzip-16.md) metadata URI that binds a hash of the registry bytes. It decides its own visibility: a public chain, a consortium, or a narrower anchor. This recipe repository holds the format and synthetic examples only. A real ecosystem MUST publish the live registry somewhere else, and MUST NOT treat the example file in this repository as its freezer list.

A JSON file in a recipe repository cannot prove that a freezer exists. The anchor is how a reader tells a published registry from an invented one. A readable Tezos Domains name (principle 4) helps, and it does not replace the anchor.

## 10. Interoperability first

Descriptive metadata SHOULD use standards that already exist: MIABIS, FHIR Specimen, GA4GH DUO, SPREC, FAIR, and for the token TZIP-12 and TZIP-21. The chain carries custody, volume and lineage. The description of the material stays off-chain, referenced by URI and hash.

`attach_data` records that reference on the tube: a URI, the sha256 of the bytes, a data type (QC, a RIN, a sequencing run, an image, an analysis), the step it belongs to, and an optional licence or access level. The URI MUST be `https://` or `ipfs://` and MUST point at an access-controlled or open resource. It MUST NOT carry personal data, and neither must the resource. A viewer walks `parent_id`, so datasets recorded on a parent stay visible from a child without being copied onto the child.

A second vocabulary for sample type, consent use, or pre-analytical handling would be a new silo. Where a wallet-type field does not yet line up with a standard, the rulebook says the mapping is to be confirmed rather than inventing the link.

## 11. Test only on testnets, with synthetic data

Tests MUST run on a public testnet, and MUST use synthetic data only. Real tube codes, donor or owner records, and production keys MUST NOT be committed to this repository or sent to a test contract.

A testnet is public too. Synthetic codes in the `SY000001xx` series, and the placeholder addresses in the wallet-registry example, are the pattern to follow.

## 12. Open recipe

The recipe may be adapted freely. Improvements SHOULD be shared where that is possible, as a pull request or as a public fork. An adaptation does not have to come back here to be legitimate.

Another biobank's fork is part of the point. This is a shared design, not a product and not a patentable invention.
