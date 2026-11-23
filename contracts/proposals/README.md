# Contract proposals

Patches here are proposals against `contracts/bioid_fa2.py`. They are not applied to the contract in this directory and not originated anywhere. The lean21 mainnet trial contract is history and is never re-originated; a proposal that is accepted is tested on a testnet first.

## v0.4-integrity.patch

Compiled with `smartpy-tezos==0.24.2`; the existing `bioid_happy` and `bioid_rejections` scenarios pass, and a new `bioid_volume` scenario covers the changes. To check it:

```bash
cp contracts/bioid_fa2.py /tmp/bioid_fa2.py
patch /tmp/bioid_fa2.py contracts/proposals/v0.4-integrity.patch
cd /tmp && python3 bioid_fa2.py
```

1. **Volume conservation by transformation type.** `transform` takes a new `added_ul : option nat`. Conservation applies to the source material consumed (`burn_ul`), never more than the balance. `aliquoted` and `split` add no liquid: `added_ul` must be `None` and the children are capped by `burn_ul`. `rna_isolation` and `dna_isolation` (extraction, elution) may produce more volume than was drawn; if `added_ul` is given, children are capped by `burn_ul + added_ul`. New reasons `dilution` and `titration` must give `added_ul` and are capped by `burn_ul + added_ul`. The `TRANSFORM` event carries `added`. Error: `BIOID_VOLUME`.
2. **`confirm_destroyed` is custodian-only.** The owner orders destruction with `withdraw`; the custodian holding the tube attests it. One key does not do both.
3. **`adjust_volume`** emits the previous volume, and only `measured` may raise a volume.
4. **`unfreeze_anonymised` runs once** (the root must still be `frozen`).

Signature change: `transform` gains a parameter, so the bridge `TezosBackend` and the viewer parser need a matching update when this is adopted (sprint day 4).
