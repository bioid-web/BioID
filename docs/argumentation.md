---
title: "Why BioID: argumentation for an open chain-of-custody layer for biobank samples"
subtitle: "Evidence-based case for a Tezos FA2 inventory and lineage system"
date: "19 October 2026"
---

**BioID concept note** · Independent side project. Nothing deployed. Citations are to publicly available sources; where a claim could not be verified it is omitted or flagged.

## 1. Elevator pitch

biobank science depends on knowing what a tube is, where it has been, how much is left, and whether the owner may still use it. Those facts are today scattered across local LIMS systems that partners cannot independently audit. **BioID** proposes an open, tamper-evident layer on Tezos: one FA2 token per physical tube (balance = volume in µL), process and transit wallets for mid-flight states, a lineage tree for derived samples, and consent withdrawal via freeze-then-burn plus crypto-shredding of the off-chain donor link. It is an **open LIMS layer**—chain of custody and inventory that complements existing systems, mapped to MIABIS/FAIR/FHIR/GA4GH vocabularies, not a replacement for clinical or consent software. Interoperability is a design goal, not an afterthought.

## 2. Problems the system addresses (with evidence)

### 2.1 Traceability and chain-of-custody gaps

ISO 20387:2018 requires biobanks to ensure traceability of biological material and associated data from collection/acquisition or reception through distribution, disposal or destruction, and to maintain critical chain-of-custody records for transport from dispatch to receipt, including deviations that affect integrity.[^iso20387][^iso20387-checklist] ISBER Best Practices likewise call for inventory and tracking from collection through storage, distribution or disposal, with contemporaneous, traceable records and shipping manifests.[^isber] In practice many collections still rely on siloed LIMS tables and paper shipping notes that partners cannot verify independently.

### 2.2 Sample mix-ups, preanalytical variables and irreproducibility

Misidentified and contaminated cell lines remain a well-documented cause of wasted and irreproducible research. ICLAC summarises worldwide surveys showing misidentification rates often in the range of about 10–100%, with an average near 22%.[^iclac] Preanalytical factors (warm/cold ischemia, centrifugation, storage) systematically affect downstream assays; the ISBER-backed Standard PREanalytical Code (SPREC) exists precisely so those variables can be recorded and compared across sites.[^sprec][^sprec4] A shared, immutable custody log does not replace authentication assays, but it makes provenance and handling history inspectable when results conflict.

### 2.3 Poor visibility and underuse of stored samples

A global survey of 276 biobanks found that a majority reported utilisation of 10% or less, with target rates often 2.5–5× higher than actual use; underutilisation was framed as a threat to operational, financial and social sustainability, including donor trust.[^henderson] A later hospital-biobank analysis reported that over 6–7 years only about 3.5% of aliquots were used, while roughly a quarter of submissions and just over half of collections were accessed at least once—illustrating how metric choice matters, but also how large stocks can sit unused.[^meduni] Better cross-site discoverability of *what exists and is still usable* is a precondition for higher utilisation.

### 2.4 Trust and benefit-sharing between collections and partners

Material transfers between institutions rest on MTAs and trust that the shipping party recorded the hand-over correctly. When custody is only in one organisation’s database, the receiving lab cannot independently prove when a shipment left, sat in transit, or arrived. OECD guidelines on human biobanks emphasise governance, access, privacy and benefit-sharing as conditions for sustainable repositories.[^oecd] An open, dual-signed ship/`receive` trail strengthens that trust without requiring a shared vendor.

### 2.5 Consent management and withdrawal

GDPR Article 17 grants a right to erasure (“right to be forgotten”) under specified conditions, with research-related derogations that must be interpreted carefully.[^gdpr17] EDPB Guidelines 02/2025 on blockchain advise that storing personal data on-chain should generally be avoided; where blockchain is used, controllers should minimise on-chain personal data, prefer off-chain storage with proofs, design for erasure/anonymisation, and conduct a DPIA.[^edpb] Dynamic-consent systems such as Dwarna (Malta Biobank) already explore blockchain as an immutable consent-change log while keeping identifying links off-chain so that erasure can sever linkability.[^dwarna] BioID’s opaque `consent_ref` plus freeze-then-burn and crypto-shredding follows the same logic for the *sample lineage*, not only the consent flag.

### 2.6 Fragmented LIMS across institutions

Each biobank’s LIMS is optimised for local operations. Cross-institution exchange usually means CSV exports, email, or proprietary APIs. ISO 20387 explicitly asks biobanks to make reasonable efforts to support **interoperability** of information and data related to biological material, and to provide interested parties with access to a catalogue of available material.[^iso20387-interop] BBMRI-ERIC’s Directory (MIABIS-based, REST API; hundreds of biobanks and thousands of collections) shows demand for shared discovery without a single shared LIMS.[^directory][^miabis]

### 2.7 One Health and cross-sector sharing

One Health work requires human, animal and environmental samples to be findable and shareable under clear access rules. BBMRI-ERIC has published knowledge-base material on biobanks and the One Health approach;[^onehealth-bbmri] WHO’s BioHub and the OHHLEP structure illustrate policy pressure for safer, faster pathogen and sample exchange across sectors.[^biohub][^ohhlep] MIABIS already allows sample source values including Human, Animal and Environment.[^miabis-attrs] Custody layers that are not locked to one clinical vendor help that exchange.

## 3. How the design answers each problem

| Problem | BioID feature |
|---|---|
| Traceability / CoC gaps | MOVE + RECEIVE events; process and transit wallets; full indexer history |
| Mix-ups / preanalytics | Per-tube token + lineage; off-chain SPREC/MIABIS metadata referenced by URI/hash |
| Underuse / invisibility | Public (or consortium-visible) wallet inventory in µL; status includes frozen/withdrawn |
| Partner trust | Two-step ship/`receive`; both custodians sign the hand-over |
| Consent withdrawal | Opaque `consent_ref`; freeze lineage; `confirm_destroyed`; crypto-shred register |
| Fragmented LIMS | Adapters to local LIMS; FA2 so any wallet/indexer can read balances |
| One Health sharing | Neutral token model; no central owner of the ledger; MIABIS-compatible metadata off-chain |
| **Interoperability** | Standards mapping (§4); open FA2/TZIP-12 + TZIP-21; Directory/FHIR/GA4GH hooks |

## 4. Interoperability (major design goal)

Interoperability here means: another biobank, partner lab, indexer or regulator can **discover, interpret and reconcile** sample custody and minimal metadata without adopting BioID’s LIMS or Tezos-only tooling. The design treats interoperability at five layers.

### 4.1 Sample and data standards (semantics)

- **MIABIS / BBMRI-ERIC.** MIABIS defines minimal attributes for biobanks, collections, samples and donors; Sample IDs are intended for sharing and should be pseudonymised and persistent within a biobank.[^miabis][^miabis-sample] Off-chain BioID metadata (type, storage temperature, creation time, parent links) should map to MIABIS fields; the on-chain token points to that record by URI + hash.
- **BBMRI-ERIC Directory.** The Directory is a MIABIS-based catalogue with a documented REST API for discovery of biobanks and collections.[^directory] BioID does not replace the Directory; it can supply verifiable custody and stock signals *after* a collection is found there.
- **ISO 20387.** Clause 7.10 requires a tracking system and reasonable efforts toward interoperability of information and data; catalogues of available material are encouraged.[^iso20387-interop] BioID is one technical response to that clause for custody/inventory. **ISO 21899:2020** addresses validation/verification of *processing methods*, not IT interfaces; it complements ISO 20387 on method quality and should not be misread as an API standard.[^iso21899]
- **FAIR (especially “I”).** Wilkinson et al. require (meta)data to use FAIR-compliant vocabularies and to include qualified references to other (meta)data.[^fair] BioID keeps rich metadata off-chain in FAIR form; the chain stores durable identifiers and content hashes so references stay resolvable and integrity-checkable.
- **HL7 FHIR Specimen.** FHIR R5 Specimen models identifiers, type, parent specimens, collection, processing, containers and quantity—aligned with BioID’s per-tube + lineage + volume model.[^fhir] A LIMS adapter can project FA2 balances and parent links into FHIR Specimen resources for hospital/lab exchange.
- **GA4GH DUO (and Beacon).** DUO provides machine-readable data-use permissions (e.g. GRU, HMB, DS) used to tag datasets and streamline access decisions; Beacon exposes data-use conditions for discovery.[^duo][^duo-paper] Consent/use codes belong off-chain (or as opaque refs); they should be encoded with DUO rather than free text so partner DACs can interpret them.
- **SPREC.** SPREC codes the main preanalytical variables for fluids and solids and is referenced by ISBER practice and biobank IT implementations.[^sprec][^sprec4] Store SPREC in the off-chain record; optionally hash it on-chain for integrity.

### 4.2 Integration with existing LIMS (not replacement)

BioID is an **open LIMS layer**: scanners and the local LIMS remain the system of entry; a signing service emits `move` / `receive` / `transform` / `consume` / `withdraw` operations. Reconciliation goes both ways (indexer → LIMS). That matches how Dwarna and other blockchain biobank pilots keep clinical/consent data off-chain while putting an audit trail on-chain.[^dwarna][^cmpb]

### 4.3 Open token and metadata standards (machine readability)

FA2 (TZIP-12) is Tezos’s multi-asset token standard (`transfer`, `balance_of`, `update_operators`), so any compliant wallet, indexer or explorer can read balances without a proprietary SDK.[^fa2] TZIP-21 defines rich token metadata (name, decimals, attributes, URIs) so off-chain catalogues and on-chain tokens stay linked in a standard JSON shape.[^tzip21] That is the opposite of a closed silo: **the ledger is readable with public tooling**.

### 4.4 Cross-institution and cross-sector exchange without a central owner

A public or consortium Tezos ledger has no single institutional “owner” of the custody record. Custodian roles and `receive` rights encode organisational boundaries; transit wallets encode shipments. One Health exchange (human/animal/environment) can share the same token mechanics while keeping sector-specific metadata and access rules off-chain under MIABIS/DUO.[^onehealth-bbmri][^miabis-attrs]

### 4.5 Identifiers

Primary keys are the printed **2D Data Matrix / tube codes** (on-chain as token codes, optionally opaque). Collection-level catalogues may additionally use persistent identifiers (DOIs, ARKs) in off-chain MIABIS/Directory records—those PIDs are not required on every tube token. FHIR Specimen.identifier / accessionIdentifier provide a clinical bridge.[^fhir][^miabis-sample]

### 4.6 Bridges to other chains (cautious)

Cross-chain bridges (e.g. toward Ethereum or Solana ecosystems) are **optional and should be treated as high-risk**. They add oracle and bridge-security failure modes and are not required for BioID’s core value (Tezos-native FA2 + indexers). If ever used, they should carry only non-personal proofs (hashes, token IDs), never donor-linkable data, and only after a DPIA.[^edpb]

### 4.7 Objection: “Isn’t this just another silo?”

| Risk of a new silo | How BioID is designed to avoid it |
|---|---|
| Proprietary data model | Map to MIABIS, FHIR Specimen, SPREC, DUO |
| Vendor lock-in for reading state | FA2/TZIP-12 + public indexers (e.g. TzKT) |
| Replace every LIMS | Explicit complement via APIs/adapters |
| Discovery monopoly | Remain compatible with BBMRI-ERIC Directory / Negotiator |
| Chain lock-in for semantics | Semantics live off-chain in open standards; chain holds custody proofs |

Interoperability fails if BioID invents parallel vocabularies. The rule is: **custody and volume on-chain; meaning in shared standards off-chain.**

## 5. Fit with requirements and frameworks

- **ISO 20387:** end-to-end traceability; transport chain of custody; information management and interoperability efforts; catalogue access.[^iso20387][^iso20387-interop][^iso20387-checklist]
- **ISO 21899:** method validation/verification for processing—supports quality claims about *how* material was processed, complementary to custody logs.[^iso21899]
- **BBMRI-ERIC / MIABIS / Directory:** shared metadata and discovery.[^miabis][^directory]
- **FAIR:** findable identifiers, accessible protocols, interoperable vocabularies, reusable with clear licence/provenance.[^fair]
- **GDPR:** data minimisation (Art. 5); erasure (Art. 17); pseudonymisation; DPIA for high-risk processing. Exact legal design to be confirmed with the data protection officer of the biobank operating the system.[^gdpr17][^edpb]
- **EDPB 02/2025:** avoid on-chain personal data; prefer off-chain + commitments/hashes; design erasure by unlinking; justify public chains only when publicity is necessary for the purpose.[^edpb]
- **Nagoya Protocol:** for genetic resources within scope, access and benefit-sharing obligations and the ABS Clearing-House matter for *material* legality; BioID can record custody and reference ABS documentation off-chain by hash/URI, but does not itself issue internationally recognised certificates.[^nagoya]
- **OECD HBGRD guidelines:** governance, consent, access, privacy, benefit-sharing for human biobanks and genetic research databases.[^oecd]

## 6. Why Tezos (stated fairly)

| Property | Relevance to BioID | Source |
|---|---|---|
| **FA2 multi-asset (TZIP-12)** | One contract, many tube `token_id`s; standard wallets/indexers | [^fa2] |
| **TZIP-21 metadata** | Standard link from token to off-chain FAIR/MIABIS record | [^tzip21] |
| **Low fee / PoS energy profile** | High volume of small custody events; PwC/Nomadic Labs LCA reported a small network energy footprint relative to PoW chains (see report for methods and figures) | [^tezos-lca][^tezos-pwc] |
| **On-chain governance / self-amendment** | Protocol can evolve without a hard-fork culture hostile to long-lived institutional apps | [^tezos-gov] |
| **Michelson / formal methods culture** | Safety-critical custody logic benefits from languages and tooling aimed at verification | [^tezos-fv] |
| **Tezos Domains (`.tez`)** | Human-readable names (e.g. project branding) resolving to addresses—optional UX, not core safety | [^tezdom] |

Tezos is a fit, not a monopoly: the *argument* is open, standard tokens + low operational overhead + governance longevity. A permissioned Tezos deployment or rollup remains available if a DPIA rejects full publicity.[^edpb]

## 7. Prior art and how BioID differs

| Project / paper | What it did | Where BioID differs |
|---|---|---|
| **Dwarna** (EJHG 2020) | Hyperledger Fabric log of dynamic consent changes; off-chain identity links; GDPR erasure via unlinking | Focus on **physical tube custody, volume and lineage**; consent is a reference + withdrawal workflow, not the only payload |
| **CMPB 2023** Hyperledger biobank PoC | Permissioned chain for biobank process steps (consent, processing, storage, transfer) | Public/consortium-readable **FA2 inventory**; process/transit wallets; freeze-then-burn withdrawal |
| **Decentralised biobanking / organoid NFT pilots (2025)** | ERC-style NFTs for specimen/organoid tracking and patient apps | Tezos FA2 with **volume as balance**; explicit CoC states; standards mapping for MIABIS/FHIR/DUO |

BioID’s distinctive combination is: **per-tube fungible volume + lineage transforms + mid-state wallets + interoperable off-chain semantics + consent withdrawal that never runs ahead of physical destruction.**

## 8. Strongest objections and honest rebuttals

**“Why not just a database / LIMS?”**  
A LIMS is still required. What a shared ledger adds is independent verifiability across custodians who do not share a vendor or trust each other’s admin rights. ISO 20387’s interoperability and catalogue expectations already push beyond a single private DB.[^iso20387-interop]

**“GDPR vs immutability.”**  
EDPB 02/2025: do not put personal data on-chain in clear text; use off-chain storage and unlinkability for erasure.[^edpb] BioID stores opaque codes and hashes; the consent register and salt are deletable. Residual risk remains for pseudonymous public inventories—hence DPIA and optional opaque codes/wallet labels.

**“Public inventories expose sensitive stocks.”**  
Valid. EDPB says public chains only when publicity is necessary for the purpose.[^edpb] Mitigations: permissioned validators, opaque tube codes, coarse wallet labels, or hash-anchoring for selected collections.

**“Oracle problem: garbage in, gospel out.”**  
The chain only records what scanners/signing keys assert. Mitigation: dual-control `receive`, stuck-tube monitors, LIMS reconciliation, and never treating on-chain state as a substitute for physical QC or authentication assays.[^iclac]

**“Key management and custodian compromise.”**  
Custodian HSM/KMS, multisig governance, operator rotation, and owner override on withdrawal limit blast radius; they do not eliminate insider threat.

**“Cost and adoption.”**  
Per-tube tokens increase storage burn relative to a single status row; pilots should start on a public testnet and measure fees. Adoption hinges on LIMS adapters and Directory-compatible metadata, not on asking labs to abandon existing tools.

**“Regulatory acceptance.”**  
ISO 20387 / ISBER speak to *requirements*, not to blockchain per se. Acceptance will follow demonstrated audit utility and DPIA outcomes, not white papers alone.

**“Interoperability: another silo?”**  
Addressed in §4.7: open token standard + mapping to MIABIS/FHIR/SPREC/DUO + Directory coexistence.

## 9. Five strongest arguments (pitch / grant ready)

1. **Independent, cross-institution chain of custody** — ISO 20387 and ISBER already require end-to-end traceability and transport CoC; BioID makes that history verifiable by partners who do not share a LIMS.[^iso20387][^isber]
2. **Interoperability by design** — MIABIS, BBMRI-ERIC Directory, FHIR Specimen, GA4GH DUO, SPREC and FAIR carry meaning; FA2/TZIP-12/TZIP-21 make custody machine-readable without a proprietary reader—avoiding a new silo.[^miabis][^fhir][^duo][^fa2]
3. **Live inventory and underuse** — when most biobanks report very low utilisation, a shared view of *what is still available and where* is a practical lever for sharing and sustainability.[^henderson]
4. **Consent withdrawal that respects both GDPR and physics** — freeze-then-burn plus off-chain crypto-shredding matches EDPB guidance to minimise on-chain personal data and design for unlinkable erasure.[^edpb][^gdpr17]
5. **One Health and multi-custodian exchange without a central owner** — human/animal/environment collections can share custody mechanics while keeping sector rules in standard off-chain vocabularies.[^onehealth-bbmri][^miabis-attrs]

## 10. References

[^iso20387]: ISO 20387:2018, *Biotechnology — Biobanking — General requirements for biobanking*. https://www.iso.org/standard/67888.html  
[^iso20387-checklist]: Assessor checklist materials reproducing ISO 20387 transport CoC text (e.g. BLQS application form citing 7.4.2). https://blqs.dmsc.moph.go.th/th/download/3854/km/2479  
[^iso20387-interop]: ISO 20387:2018 clause 7.10 (management of information and data), including interoperability and catalogue expectations — as reproduced in public training/PDF extracts, e.g. https://www.nms.unl.pt/Portals/0/adam/NMS%20Generic%20Content/RhjtOeouiUiHL7bKRcXnIA/Description/ISO_20387_2018_General%20requirements%20for%20biobanking.pdf  
[^iso21899]: ISO 21899:2020, *Biotechnology — Biobanking — General requirements for the validation and verification of processing methods for biological material in biobanks*. https://www.iso.org/standard/72118.html  
[^isber]: ISBER, *Best Practices for Repositories* (5th ed. overview). https://www.isber.org/page/BPR  
[^iclac]: ICLAC, *Institutional Best Laboratory Practices for Cell Line and Tissue Sample Authentication* (2023), citing average misidentification ≈22%. https://iclac.org/wp-content/uploads/ICLAC-Institutional-Best-Lab-Practices-Cell-Line-Authentication_COMBO-2023.pdf  
[^sprec]: Betsou et al., “Standard Preanalytical Coding for Biospecimens… (SPREC),” *Biopreserv Biobank* (2012). https://doi.org/10.1089/bio.2012.0012 ; ISBER SPREC page: https://www.isber.org/page/SPREC  
[^sprec4]: SPREC v4.0 short communication (2025) noting ISO 20387/ISBER references to SPREC. https://kankerregister.org/en/publicaties/standard-preanalytical-code-version-40  
[^henderson]: Henderson et al., “Advancing Professionalization of Biobank Business Operations: Performance and Utilization,” *Biopreserv Biobank* (2019). https://doi.org/10.1089/bio.2019.0005  
[^meduni]: “Utilization Patterns of Hospital Biobank Samples…,” *J Clin Med* (2026). https://doi.org/10.3390/jcm15114292  
[^oecd]: OECD, *Guidelines on Human Biobanks and Genetic Research Databases* (2009). https://legalinstruments.oecd.org/en/instruments/OECD-LEGAL-0375  
[^gdpr17]: Regulation (EU) 2016/679, Article 17. https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679  
[^edpb]: EDPB, *Guidelines 02/2025 on processing of personal data through blockchain technologies* (consultation PDF, 8 Apr 2025). https://www.edpb.europa.eu/system/files/2025-04/edpb_guidelines_202502_blockchain_en.pdf ; landing page: https://www.edpb.europa.eu/documents/guideline/guidelines-022025-on-processing-of-personal-data-through-blockchain_en  
[^dwarna]: Mamo et al., “Dwarna: a blockchain solution for dynamic consent in biobanking,” *Eur J Hum Genet* (2020). https://doi.org/10.1038/s41431-019-0560-9  
[^cmpb]: “Increasing the security and traceability of biological samples in biobanks by blockchain technology,” *Comput Methods Programs Biomed* (2023). https://doi.org/10.1016/j.cmpb.2023.107379  
[^miabis]: BBMRI-ERIC, “Introducing MIABIS…”. https://www.bbmri-eric.eu/howtomiabis/ ; GitHub: https://github.com/BBMRI-ERIC/miabis  
[^miabis-sample]: MIABIS Sample component attributes. https://miabis.bbmri-eric.eu/Sample+Donor+Event/V1.1/Data-describing-Sample.html  
[^miabis-attrs]: MIABIS attributes list (incl. sample source Human/Animal/Environment). https://github.com/BBMRI-ERIC/miabis/blob/master/all%20attributes.md  
[^directory]: BBMRI-ERIC Directory. https://directory.bbmri-eric.eu/ERIC/directory ; Common Service IT (Directory + MIABIS + API). https://www.bbmri-eric.eu/bbmri-eric/common-service-it/  
[^fair]: Wilkinson et al., “The FAIR Guiding Principles…,” *Sci Data* (2016). https://doi.org/10.1038/sdata.2016.18  
[^fhir]: HL7 FHIR R5 Specimen. https://hl7.org/fhir/R5/specimen.html  
[^duo]: GA4GH Data Use Ontology (DUO). https://www.ga4gh.org/product/data-use-ontology-duo/  
[^duo-paper]: “The Data Use Ontology to streamline responsible access…,” *Cell Genomics* (2021). https://www.cell.com/cell-genomics/pdfExtended/S2666-979X(21)00035-5  
[^onehealth-bbmri]: BBMRI-ERIC knowledge base, “Biobanks and One Health approach”. https://www.bbmri-eric.eu/knowledgebase/biobanks-and-one-health-approach/  
[^biohub]: WHO BioHub. https://www.who.int/initiatives/who-biohub/  
[^ohhlep]: WHO, One Health High-Level Expert Panel (OHHLEP). https://www.who.int/groups/one-health-high-level-expert-panel  
[^nagoya]: Nagoya Protocol (CBD). https://www.cbd.int/abs/doc/protocol/nagoya-protocol-en.pdf  
[^fa2]: Tezos Docs, FA2 tokens; TZIP-12. https://docs.tezos.com/architecture/tokens/FA2 ; https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/tzip-12.md  
[^tzip21]: TZIP-21 Rich Metadata. https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-21/tzip-21.md  
[^tezos-lca]: Tezos life-cycle assessment PDF (Nomadic Labs / PwC France). https://tezos.com/2021-12-06-Tezos-LCA-Final.pdf  
[^tezos-pwc]: Announcement of Nomadic Labs–PwC France environmental footprint analysis. https://www.tzapac.com/articles/nomadic-labs-partners-with-pwc-in-france-to-analyze-the-tezos-blockchains-environmental-footprint/  
[^tezos-gov]: Tezos Docs, Governance and self-amendment. https://docs.tezos.com/architecture/governance  
[^tezos-fv]: OpenTezos overview of formal verification for Michelson. https://opentezos.com/formal-verification/modeling-theorem/  
[^tezdom]: Tezos Domains. https://tezos.domains/en  

### Claims not fully verified / used cautiously

- Exact numeric energy figures from the PwC/Tezos LCA are **not restated here as precise facts** beyond pointing to the published PDF; readers should take numbers from that report directly.
- EDPB Guidelines 02/2025: the April 2025 consultation PDF was verified; later “final” adoption notices exist on the EDPB site—controllers should use the latest adopted text when implementing.
- ISO 20387 full paid text was not purchased; interoperability/CoC citations rely on the official abstract page plus widely circulated clause extracts and assessor checklists—**re-check against a licensed copy before audit claims**.
- Decentralised biobanking NFT pilots (2025) are summarised at a high level from search metadata; BioID’s differentiation does not depend on their internal details.
