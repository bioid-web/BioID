# Security and privacy

## No personal or real sample data

This repository must not contain personal data or real biobank material. Do not commit:

- names, contact details, dates of birth, or government or holder identifiers
- donor, participant or animal-owner records, including the mapping behind a `consent_ref`
- real tube codes, Data Matrix payloads, LIMS exports, shipping manifests or freezer maps
- photographs of real tubes, racks or labels
- coordinates or other location data that identifies a holding or a person

Examples, tests, fixtures and screenshots must use synthetic data only. The `SY000001xx` series in the concept note is invented. New examples must be invented too, and labelled synthetic.

Do not commit hashes of personal identifiers. Low-entropy hashes can be reversed.

If you find data that should not be here, remove it in a new commit and treat the old commit as sensitive. History rewrites need the repository maintainers.

## Secrets

Do not commit private keys, custodian seeds, API tokens, `.env` files, or signing-service credentials. Location wallets in the design are not meant to have their own keys; if a key is ever created for a test, keep it out of git.

## Reporting a problem

Nothing in this repository is deployed. If a report itself would reveal personal data, a secret, or a real sample, use a private GitHub security advisory (Security → Advisories) rather than a public issue. Design questions that do not reveal such data can be issues.

## What this file is

The [concept note](docs/concept-note.md) describes the privacy design: no personal data on-chain, an opaque consent reference, and crypto-shredding of the off-chain link when consent is withdrawn. This file is the rule for the repository. It is not a legal opinion, and it does not replace a DPIA or a data-protection review by anyone who later operates a system like this.
