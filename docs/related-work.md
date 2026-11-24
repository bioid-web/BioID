---
title: Related work
---

# Related work and what BioID borrows

Survey for white paper v0.4, made on 24 November 2026. Every link was opened or its DOI resolved through Crossref on that date. Descriptions are limited to what each source says about itself; nothing here is an endorsement.

BioID is narrower than most projects below. It records the custody, volume and lineage of physical tubes and the withdrawal of consent across every derived tube. It does not trade data, hold personal data, or give donors wallets.

## 1. Consent on a ledger

| Project | What it does | What BioID takes from it | Where BioID differs |
|---|---|---|---|
| **Dynamic consent** (Kaye et al., *Eur J Hum Genet* 2015; [doi:10.1038/ejhg.2014.71](https://doi.org/10.1038/ejhg.2014.71)) | Defines dynamic consent: a digital interface through which participants can follow and change their consent over time. | The reason a withdrawal must reach every derived tube, quickly and visibly. | BioID records the institution's execution of a withdrawal. It is not a participant interface. |
| **Dwarna** (Mamo et al., *Eur J Hum Genet* 2019; [doi:10.1038/s41431-019-0560-9](https://doi.org/10.1038/s41431-019-0560-9); [code](https://github.com/NicholasMamo/dwarna)) | Dynamic consent for a biobank on a permissioned ledger (Hyperledger Fabric), with identifying data kept off-chain for GDPR erasure. | Keep identity off-chain so erasure means deleting the off-chain link. | Public chain; physical custody and volume are on-chain; consent text stays off-chain. |
| **ConsentChain** (Albalwy, Brass, Davies, *JMIR Med Inform* 2021; [doi:10.2196/27816](https://doi.org/10.2196/27816)) | Ethereum smart contracts for patients, data creators and requesters to grant, withdraw and request access to clinical genomic data held off-chain; machine-readable consent codes. Notes that verifying user credentials is still open. | Machine-readable use conditions (BioID already uses GA4GH DUO codes in `request_access`); the credential gap is real and is listed in our threat model. | No patient keys. Access is recorded per tube and per agreement fingerprint. |
| **Demonstrated consent** (*Am J Bioeth* 2024/2025; [doi:10.1080/15265161.2024.2416117](https://doi.org/10.1080/15265161.2024.2416117)) and a critical response ([doi:10.1080/15265161.2025.2470646](https://doi.org/10.1080/15265161.2025.2470646)) | One NFT per donated sample whose metadata records planned and past uses, explained to donors by a language model. The response questions whether technology builds trust. | One token per physical sample. | Tokens are stewardship records, not donor assets; no AI explanation layer; the trust question is answered by what the record can and cannot prove (threat model). |

## 2. Biobanks, clinical research and genomics on a ledger

- **de-bi**, a decentralised biobanking platform for organoid research networks (*Frontiers in Blockchain* 2025; [doi:10.3389/fbloc.2025.1510429](https://doi.org/10.3389/fbloc.2025.1510429)). ERC-1155 tokens on Ethereum, including soulbound identity tokens and transferable specimen tokens; the authors expect to need a layer 2 for cost. This is the closest design. BioID differs in volume as the token balance, one token per physical container, disabled free transfer (custody moves only through typed `move`, `ship` and `receive`), enforced wallet-type transitions, and a two-step hand-over between sites.
- **Blockchain for clinical research quality** (Benchoufi & Ravaud, *Trials* 2017; [doi:10.1186/s13063-017-2035-z](https://doi.org/10.1186/s13063-017-2035-z)) and **distributed ledgers in biomedicine** (Kuo, Kim & Ohno-Machado, *JAMIA* 2017; [doi:10.1093/jamia/ocx068](https://doi.org/10.1093/jamia/ocx068)) set out the general case: time-stamped, tamper-evident records of protocol and consent steps, and the limits (garbage in, scalability, privacy). BioID's threat model uses the same split between what a ledger proves and what it cannot.
- **Genomics and blockchains** (Ozercan et al., *Genome Research* 2018; [doi:10.1101/gr.207464.116](https://doi.org/10.1101/gr.207464.116)) reviews genomic data-sharing and marketplace designs.

## 3. Data markets and personal genomics

- **Nebula Genomics**, described in Grishin, Obbad & Church, *Nature Biotechnology* 2019 ([doi:10.1038/s41587-019-0271-3](https://doi.org/10.1038/s41587-019-0271-3)): privacy-preserving genomic data sharing in which individuals control access to their own data.
- **Genomes.io** ([genomes.io](https://genomes.io/)): an encrypted "DNA vault" with an Ethereum audit log of access and a utility token for rewards.
- **Ocean Protocol Compute-to-Data** ([docs](https://docs.oceanprotocol.com/developers/compute-to-data)): sensitive datasets stay on-premise and buyers run approved algorithms against them.

*What BioID takes:* an audit log of access is valuable on its own, and compute-to-data is a good pattern for future result delivery (white paper §7). *Where BioID differs on purpose:* no data sale, no payment token and no donor wallets. Tokens record custody and access, which keeps samples from looking like speculative assets.

## 4. Supply-chain provenance standards and networks

- **GS1 EPCIS 2.0** (ISO/IEC 19987:2024; [standard](https://ref.gs1.org/standards/epcis/2.0.1/)) and the **Core Business Vocabulary** ([CBV](https://ref.gs1.org/standards/cbv/)). ObjectEvent fits ship, receive and storage moves. TransformationEvent, which has input and output lists, fits splits, extractions and dilutions. *Adopted in v0.4:* the bridge can export a lineage as an EPCIS 2.0 JSON-LD document (`bioid-bridge export-epcis`). The export was validated against the GS1 JSON schema on 24 November 2026.
- **OriginTrail** decentralised knowledge graph ([supply-chain overview](https://origintrail.io/blog/from-data-to-assets-transforming-global-supply-chains-with-origintrail-decentralized-knowledge-graph)). It anchors fingerprints of supply-chain data on public chains and uses EPCIS 2.0 and W3C Verifiable Credentials for interoperability. *Lesson:* speak the existing standards at the edges instead of inventing a new event format.
- **US Drug Supply Chain Security Act** (FDA, [DSCSA](https://www.fda.gov/drugs/drug-supply-chain-integrity/drug-supply-chain-security-act-dscsa)). An example of a regulated, interoperable, package-level tracing regime. It shows that per-item traceability between independent parties is workable when identifiers and events are standard. (A blockchain pilot website once associated with DSCSA work now serves unrelated content, so it is not cited.)

## 5. Identity, credentials and access

- **W3C Verifiable Credentials Data Model 2.0** (Recommendation, 15 May 2025; [spec](https://www.w3.org/TR/vc-data-model-2.0/)) and **Decentralized Identifiers 1.0** (Recommendation, 19 July 2022; [spec](https://www.w3.org/TR/did-1.0/)).
- **GA4GH Passports** (Voisin et al., *Cell Genomics* 2021; [doi:10.1016/j.xgen.2021.100030](https://doi.org/10.1016/j.xgen.2021.100030); [spec](https://ga4gh-duri.github.io/researcher_ids/ga4gh_passport_v1.html)) carry researcher identity and data-access permissions as signed "visas". The **Data Use Ontology** (Lawson et al., *Cell Genomics* 2021; [doi:10.1016/j.xgen.2021.100028](https://doi.org/10.1016/j.xgen.2021.100028)) gives the machine-readable use codes that BioID's `request_access` already stores.

*Adoption path (not implemented):* an access request could carry the fingerprint of a Passport visa or a Verifiable Credential that shows the requester's institution approved the use. This would close the "who is behind this wallet" gap that ConsentChain also reports, while keeping the credential itself off-chain.

## 6. Provenance models, packaging and FAIR

- **W3C PROV-O** ([spec](https://www.w3.org/TR/prov-o/)): entities, activities and agents. A BioID transform is a PROV activity that uses a parent entity and generates child entities.
- **RO-Crate** (Soiland-Reyes et al., *Data Science* 2022; [doi:10.3233/DS-210053](https://doi.org/10.3233/DS-210053)): packaging research outputs with their metadata. It fits datasets attached to a tube.
- **FAIR principles** (Wilkinson et al., *Scientific Data* 2016; [doi:10.1038/sdata.2016.18](https://doi.org/10.1038/sdata.2016.18)).

## 7. Biobank information systems and standards

- **OpenSpecimen** ([openspecimen.org](https://www.openspecimen.org/)) and **Baobab LIMS** (Bendou et al., *Biopreservation and Biobanking* 2017; [doi:10.1089/bio.2017.0014](https://doi.org/10.1089/bio.2017.0014)) are open-source biobank LIMS. They are the systems a BioID bridge would read from. BioID does not replace them.
- **ISO 20387:2018** biobanking general requirements ([iso.org](https://www.iso.org/standard/67888.html)), including traceability.

## 8. Regulation

- **EDPB Guidelines 02/2025 on processing of personal data through blockchain technologies** (version 2.0 adopted 7 July 2026; [page](https://www.edpb.europa.eu/documents/guideline/guidelines-022025-on-processing-of-personal-data-through-blockchain_en), [PDF](https://www.edpb.europa.eu/system/files/2026-07/edpb_guidelines_202502_blockchain_v2_en.pdf)). Controllers should document why a blockchain is needed and which type, and keep personal data off-chain, putting only commitments or pointers on-chain. BioID's design follows that line: tube codes with no personal meaning, salted fingerprints for guessable documents, and consent links held off-chain. The guidelines also mean an adopter needs a DPIA that answers their four evaluation questions.

## 9. Tezos building blocks used in v0.4

- **FA2 / TZIP-12** ([proposal](https://gitlab.com/tezos/tzip/-/blob/master/proposals/tzip-12/tzip-12.md)), the token standard.
- **TzSafe** multisig ([contracts](https://github.com/marigold-dev/tzsafe), [docs](https://docs.tzsafe.org/)), a suitable home for the institutional withdrawal-owner role. Owners and the threshold are changed by the multisig's own proposals, so owner keys rotate without any change to the BioID record.
- **TzKT API** ([api.tzkt.io](https://api.tzkt.io/)). Single bigmap keys, value filters and event payload filters make the viewer's per-tube reads possible.

## Positioning summary

| | Physical custody per container | Volume as balance, conservation rules | Withdrawal reaches all derivatives | Public, independent verification | Donor holds keys | Standard export |
|---|---|---|---|---|---|---|
| Dwarna | – | – | consent only | permissioned | – | – |
| ConsentChain | – | – | access only | Ethereum | patient | – |
| Demonstrated consent | per sample (NFT) | – | uses recorded | public chain | donor-facing | – |
| de-bi | specimen tokens | – | – | Ethereum | identity tokens | – |
| Genomes.io / Nebula | – (data) | – | access revocation | partly | individual | – |
| EPCIS networks | per item | class quantities | – | depends on network | – | EPCIS |
| **BioID v0.4** | **one token per tube** | **yes, by step type** | **yes, one write on the root** | **Tezos mainnet / testnet** | **no (institutional owner)** | **EPCIS 2.0 export (prototype)** |

"–" means the source does not describe the feature; it does not mean the project could not add it.
