# Contributing

BioID is an open recipe. Fork it and adapt it. A biobank can change wallets, reason codes, metadata mappings and the signing setup to fit local practice, and publish that fork under the same licences. Adaptations do not need to come back here. Pull requests are welcome when a change is useful to more than one collection: corrections, clearer design notes, and later the contract and scanner.

This is an early concept. Nothing is deployed.

## What belongs here

- Corrections to the concept note and the argumentation. Keep existing citations unless you are fixing an error, and say what you checked.
- Design discussion in issues, tied to the open questions in the concept note.
- Forks and adaptations. Say what you changed and why, whether you open a pull request or keep the fork.
- Later, the FA2 contract, the scanner, and more synthetic fixtures. `contracts/` and `app/` are placeholders.

## What must not be committed

No personal data. No real sample data. No private keys or other secrets. Read [SECURITY.md](SECURITY.md) before adding an example, a fixture or a screenshot.

## Licences

Code contributions are under the MIT License ([LICENSE](LICENSE)), copyright BioID contributors. Documentation contributions, including changes to `docs/` and `examples/`, are under CC BY 4.0 ([LICENSE-docs](LICENSE-docs)).

## Previewing the docs site

The steps are in the README, under "Site (GitHub Pages)". Please do not enable GitHub Pages or change repository visibility from a pull request.
