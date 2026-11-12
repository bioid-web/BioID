# examples

Synthetic sample data only. Nothing in this folder is a real tube, donor, animal, owner or site.

[`synthetic-lineage.json`](synthetic-lineage.json) is the worked blood-sample example from the [concept note](../docs/concept-note.md) (section 5), after the last storage step. Codes in the `SY000001xx` series, the owner label `STUDY-OWNER`, the consent reference `cref-a1b2c3` and the wallet names are invented.

[`wallet-registry.example.json`](wallet-registry.example.json) is a synthetic wallet registry that covers intake, an −80 °C freezer and one rack inside it, freezer "bios", aliquoting, RNA isolation, DNA isolation, sequencing, courier transit, and a quarantine hold. Addresses are `tz1` shaped and fail checksum validation. Names such as `bios.example.tez` are not registered. The format is [`schemas/wallet-registry.schema.json`](../schemas/wallet-registry.schema.json). A real ecosystem publishes its own registry elsewhere and anchors it, as described in [Wallet types](../docs/wallet-types.md).

[`lims-events.example.jsonl`](lims-events.example.jsonl) is a synthetic LIMS event feed for that same blood sample, mapped through [`lims-mapping.example.json`](lims-mapping.example.json) (and the YAML copy) onto the registry labels. [`lims-inventory.example.json`](lims-inventory.example.json) is a matching snapshot with one deliberate mismatch on `SY00000106`. The reference bridge in [`bridge/`](../bridge/README.md) replays the feed. A second synthetic feed, with retrieval for an external user, is in [`pilot/`](../pilot/README.md). How a laboratory LIMS couples on is described in [LIMS integration](../docs/lims-integration.md).

Add further fixtures here only when they are invented and labelled synthetic. Do not commit exports from a LIMS, real Data Matrix payloads, consent-register rows, or photographs of real tubes. See [SECURITY.md](../SECURITY.md).

These files are documentation and are covered by [CC BY 4.0](../LICENSE-docs).
