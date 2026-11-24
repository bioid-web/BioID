# Contract proposals

Patches here are proposals against `contracts/bioid_fa2.py`. They are not applied to the contract in this directory and not originated anywhere. The lean21 mainnet trial contract is history and is never re-originated. A proposal that is accepted is tested on a testnet first.

Apply them in order:

```bash
cp contracts/bioid_fa2.py /tmp/bioid_fa2.py
patch /tmp/bioid_fa2.py contracts/proposals/v0.4-integrity.patch
patch /tmp/bioid_fa2.py contracts/proposals/v0.4-lifecycle.patch   # optional second step
cd /tmp && python3 bioid_fa2.py
```

Both were compiled with `smartpy-tezos==0.24.2`. All scenarios pass: `bioid_happy`, `bioid_rejections`, `bioid_volume` (integrity) and `bioid_lifecycle` (lifecycle).

## v0.4-integrity.patch

1. **Volume conservation by transformation type.** `transform` takes a new `added_ul : option nat`. Conservation applies to the source material consumed (`burn_ul`), which can never exceed the balance. `aliquoted` and `split` add no liquid: `added_ul` must be `None` and the children are capped by `burn_ul`. `rna_isolation` and `dna_isolation` (extraction, elution) may produce more volume than was drawn. If `added_ul` is given, the children are capped by `burn_ul + added_ul`. The new reasons `dilution` and `titration` must give `added_ul` and are capped by `burn_ul + added_ul`. The `TRANSFORM` event carries `added`. Error: `BIOID_VOLUME`.
2. **`confirm_destroyed` is custodian-only.** The owner orders destruction with `withdraw`; the custodian holding the tube attests it. One key does not do both.
3. **`adjust_volume`** emits the previous volume, and only `measured` may raise a volume.
4. **`unfreeze_anonymised` runs once** (the root must still be frozen).

## v0.4-lifecycle.patch (applies on top of integrity)

1. **Constant-cost withdrawal.** `withdraw` writes the outcome once, on the root (`outcomes[root_id]`), and no longer loops over the lineage. Every operation on any descendant checks the root's outcome in `p_assert_operable`, wherever the tube sits. The `by_root` set is removed. It grew with every child, and each `transform` had to read and rewrite it. Gas for `withdraw` and `transform` no longer grows with lineage size.
2. **Escalation from `stop_use`.** A root with outcome `stop_use` may later get `destroy` or `anonymise`. The `WITHDRAW` event then carries `previous = Some "stop_use"`. Nothing else can be changed or relaxed (`BIOID_FROZEN`).
3. **Anonymisation at constant cost.** `unfreeze_anonymised` removes the outcome and marks the root in a new `anonymised` big map. The `tube` view hides `consent_ref` for the whole lineage, and children created later carry an empty `consent_ref`. Chain history keeps old values, so anonymity comes from deleting the off-chain record that links `consent_ref` to a person.
4. **Explicit lineage depth.** `transform` refuses a ninth generation, root included, with `BIOID_DEPTH`. A new `depth` big map stores each derived tube's generation. The `lineage_uris` and `lineage_has` views walk 8 tubes, so they are now complete by construction instead of stopping silently.
5. **`tube` view** returns the effective status (`frozen`, `stopped`, `anonymised` or `destroyed`, derived from the root), plus `outcome`, `depth` and `owner`.

**Owner key rotation** needs no entrypoint. The withdrawal owner fixed at mint is an institutional multisig (for example a 2-of-3 TzSafe wallet), and signers rotate inside it. A `rotate_owner` entrypoint was written and tested, then removed. Keeping it would have pushed the origination operation over the protocol's 32,768-byte limit (see Size).

### Size

Compiled code in binary Michelson, measured with `octez-client convert script … to binary`, and the forged origination operation, measured with `octez-client --mode mockup originate … --verbose-signing`. Both checks run locally; nothing is sent to a network.

| Contract | Code (bytes) | Origination operation, unsigned (bytes) |
|---|---|---|
| `bioid_fa2.py` (deployed on Shadownet) | 31,629 | 31,901 |
| + integrity | 32,401 | 32,690 |
| + integrity + lifecycle | 32,249 | 32,545 |

With a 64-byte signature, the full proposal is about 32,609 bytes, about 160 bytes under the limit. The integrity patch on its own is only about 14 bytes under it. The lifecycle patch is smaller because it removes `by_root` and has `p_assert_operable` return the token, so callers do not read it twice. Any further feature needs space first. Options, measured:

- Shorter error strings (`B_` instead of `BIOID_`) save about 430 bytes.
- Attaching data only through `attach_data`, batched in the same operation group, would remove one inlined copy of the attachment code from each custody entrypoint. Not measured yet.

**Shadownet dry run, 24 November 2026.** Nothing was injected and no tez was spent. The full proposal (integrity + lifecycle) was simulated with `octez-client originate … --dry-run --verbose-signing` against `https://rpc.shadownet.teztnets.com`, using an existing Shadownet test account. The protocol limit (`max_operation_data_length`) is 32,768 bytes.

| Measure | Value |
|---|---|
| Operation bytes, unsigned (branch + contents) | 32,548 |
| With 64-byte signature | 32,612 (156 bytes under the limit) |
| Estimated gas | 80,717 units (limit per operation 1,040,000) |
| Storage size | 33,004 bytes (limit per operation 60,000) |
| Estimated cost | about 8.36 tez: 8.251 storage burn, 0.064 allocation, 0.041 fee |

The simulation succeeded, so the proposal fits. The node checks the size limit at injection, which was not done, so that check was made against the measured bytes above.

### Decisions (24 November 2026)

- **No `rotate_owner`.** The withdrawal owner is an institutional multisig, and its keys rotate inside the multisig. Moving the owner role to another institution is not supported in v0.4.
- **Freeing spare bytes is deferred to a later upgrade.** Before any new entrypoint is added, space must be freed first, for example with shorter error strings (about 430 bytes).

Signature change: `transform` gains `added_ul`. The bridge `TezosBackend` encodes it when `TEZOS_CONTRACT_VERSION=v0.4`. The viewer shows `added` in the timeline and derives the effective status from the root's `WITHDRAW` and `UNFREEZE` events, so it reads both contract versions.
