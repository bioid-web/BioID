# contracts

The bioid FA2 contract is [`bioid_fa2.py`](bioid_fa2.py). It is one multi-asset contract: one token id per tube, balance equal to the remaining volume in µL. Tube codes such as `SY00000201` are the external ids. The chain stores a `nat` token id and a `code_index` from the code string to that id.

## Language

SmartPy, package `smartpy-tezos` 0.24.2 (17 August 2026). Checked against [smartpy.io](https://smartpy.io/) and the package metadata on 19 October 2026. That release is current: 0.24.0 made Shadownet available in the IDE and added the scenario runner used here. The contract compiles and the scenarios run with `python3 contracts/bioid_fa2.py`. No separate LIGO binary is required.

LIGO is also maintained. SmartPy is the choice because the scenario runner and the Michelson compiler are in the same Python package, which is what this repository already uses for the bridge tests.

Install the pin with:

```bash
python3 -m pip install --user -r contracts/requirements.txt
```

## What the contract enforces

Wallet types and the transition matrix are in [Wallet types](../docs/wallet-types.md), vocabulary `bioid-wallet-types-2`. The concept note's storage sketch is the source for mint, move, transform, consume, adjust, and withdrawal. Where this contract chooses, it is recorded here.

- `mint_primary` lands in `INTAKE` or `TRANSIT`. The task list said intake only. The rulebook also allows a field collection straight into a shipment, and the worked example does that, so both are accepted. The [pilot](../pilot/README.md) mints at reception.
- `adjust_volume` sets the absolute measured volume. It does not take a delta. It is allowed on `INTAKE` and `STORAGE`.
- `transform` burns only the drawn volume. The parent token remains, including at 0 µL. Each child is a new token with `parent_id`.
- Standard FA2 `transfer` always fails with `BIOID_TRANSFER_DISABLED`. TZIP-12's operator policy is no-transfer: `balance_of` and `update_operators` stay, and an operator cannot move a tube. A bare transfer cannot carry a reason without changing the FA2 parameter type. Custody moves are `move`, `ship` and `receive`.
- `ship` then `receive` is the two-step hand-over through `TRANSIT`. A `PROCESS` wallet may ship only when its process code is `retrieval` and the tube has an approved access request.
- `EXTERNAL_USER` is the recipient wallet. `receive` into it requires that approval, and the requester must be that wallet's custodian. `report_use` records `consumed`, `returned`, or `destroyed`.
- `attach_data` records a `https://` or `ipfs://` URI, a 32-byte content hash, a data type, and the step. The same record can ride along on `move`, `transform`, `consume`, `ship` and `receive`. The off-chain view `lineage_has` walks up to eight parents, so a child shows datasets recorded on its ancestors.
- `withdraw` is signed by the owner of the root token. `destroy` and `anonymise` freeze the lineage. `stop_use` sets status `stopped`. `confirm_destroyed` burns any remaining balance and leaves the token at 0 µL with status `destroyed`. `unfreeze_anonymised` clears `consent_ref` and sets status `anonymised`.
- Token metadata follows TZIP-21: `token_info` values are UTF-8 bytes. The map includes `name` (the tube code), `symbol` (`uL`), `decimals` (`0`), `sample_type`, `created_by`, and `parent_id` (empty bytes when there is no parent).

Admin registers wallets and sets `active`. A custodian may update `label` and `metadata_uri` only. Custodians sign ordinary custody. Holding wallets have no keys of their own.

## Tests

```bash
python3 contracts/bioid_fa2.py
```

Two scenarios, `bioid_happy` and `bioid_rejections`, cover the reception-to-external-use path and the rejection codes. SmartPy writes Michelson next to the script, under `contracts/bioid_happy/` and `contracts/bioid_rejections/`. Those directories are gitignored.

## Size

A Tezos operation may carry at most 32 KB, and one operation may add at most 60 KB of storage. Helpers that touch storage are therefore `@sp.private` methods of the contract class, which SmartPy inlines, instead of module-level `@sp.effects` functions, which SmartPy compiles to a `LAMBDA` at every call site with the whole storage type spelled out twice. That change took the compiled code from about 90 KB to about 31.6 KB. The entrypoint parameter type and the storage type are unchanged, and both scenarios produce the same storage, events and errors at every step. SmartPy does not let one private method call another, so `p_maybe_attach`, `p_do_ship` and `p_do_consume` repeat the wallet lookup inline. The caller emits `SHIP` or `CONSUME` after the optional attachment, in the same order as before. Pure helpers without storage access (`assert_uri`, `assert_hash`, `status_for`, `move_allowed`, `ship_allowed`) stay at module level.

If the code grows past 32 KB again, the origination will fail with an oversized operation. Check the size after compiling with `octez-client convert script contracts/bioid_happy/step_001_cont_0_contract.tz from michelson to binary`.

## Shadownet, and only Shadownet

Checked on 19 October 2026 against [Testing on testnets](https://docs.tezos.com/developing/testnets) (updated 22 July 2026) and [teztnets.com](https://teztnets.com/teztnets.json):

- Shadownet is the primary permanent testnet for application developers.
- Chain name: `TEZOS_SHADOWNET_2025-08-07T20:00:00Z`.
- Public RPC: `https://rpc.shadownet.teztnets.com`.
- TzKT was answering at `https://shadownet.tzkt.io` (API `https://api.shadownet.tzkt.io/v1/head`, chain id `NetXsqzbfFenSTS`).
- Ghostnet has been removed. Do not use it.
- Mainnet is refused by the deploy script and by `TezosBackend`.

The script does not generate a key and does not call a faucet. You fund the admin account yourself. One synthetic demo deployment exists on Shadownet, [`KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix`](https://shadownet.tzkt.io/KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix); its addresses and operations are in [`pilot/deployments/shadownet.json`](../pilot/deployments/shadownet.json) and explained in the [pilot README](../pilot/README.md).

```bash
export TEZOS_NETWORK=shadownet
export TEZOS_RPC_URL=https://rpc.shadownet.teztnets.com
export TEZOS_KEY_REF=kms://alias/syn-custodian-lab   # or an octez alias that already exists
export TEZOS_ADMIN=tz1...                             # the address that alias controls
bash contracts/deploy/originate.sh
```

That command compiles and stops. It prints the Michelson path. To originate:

```bash
export BIOID_ORIGINATE=1
bash contracts/deploy/originate.sh
```

`BIOID_ORIGINATE=1` builds storage for `TEZOS_ADMIN` and, if `octez-client` is on `PATH`, runs:

```bash
octez-client --endpoint "$TEZOS_RPC_URL" originate contract bioid_fa2 \
  transferring 0 from "$TEZOS_KEY_REF" \
  running contracts/bioid_happy/step_001_cont_0_contract.tz \
  --init "$(cat contracts/bioid_storage/step_001_cont_0_storage.tz)" \
  --burn-cap "${BIOID_BURN_CAP:-12}"
```

Origination burns about 8 tez of storage on Shadownet (the code is about 32 KB). Before it calls `octez-client`, the script checks that the RPC reports chain id `NetXsqzbfFenSTS`. `octez-client` uses `TEZOS_CLIENT_DIR` for its key directory; keep that directory outside the repository.

The file name under `bioid_happy/` can differ; the script picks the contract `.tz` it just wrote. Copy the printed `KT1` into `TEZOS_CONTRACT` for the bridge. Do not commit the key, the storage file, or the KT1 if it is tied to a secret.

The bridge `TezosBackend` encodes `mint_primary`, `move`, `ship`, `receive`, `transform`, `consume`, `report_use` (when the source wallet is `EXTERNAL_USER`), `attach_data`, `request_access` and `approve_access`. `submit` then raises `InjectionRefused`. It does not broadcast.
