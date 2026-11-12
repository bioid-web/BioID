# bridge

Reference implementation of the [LIMS integration](../docs/lims-integration.md) bridge. It replays a synthetic event feed onto an offline ledger that behaves like a small FA2 book: one token per tube, balance in µL, parent links, and an event history.

Python 3.11 or newer. The runtime dependencies are the standard library. PyYAML is optional, and only for the YAML copy of the mapping. pytest is needed to run the tests.

This package does not deploy a contract, does not hold a key, and does not talk to mainnet. Tube codes, wallets and volumes are the synthetic examples already in [`examples/`](../examples/README.md).

## Layout

| Path | Role |
|---|---|
| `src/bioid_bridge/` | The package |
| `mapping.py` | LIMS location to wallet label, LIMS event type to MOVE / MINT / BURN / ADJUST / SHIP / RECEIVE |
| `rules.py` | Wallet-type transition checks |
| `ledger.py` | `MockLedger`, SQLite, including processed event ids and the review queue |
| `service.py` | Batching, retries, idempotency, fallback when one event in a batch is invalid |
| `tezos.py` | `TezosBackend` stub. Testnet configuration only. Cannot submit |
| `reconcile.py` | LIMS snapshot versus ledger |
| `cli.py` | `replay`, `history`, `inventory`, `reconcile` |

## Run the example

From this directory, with `PYTHONPATH=src` (or after `pip install -e .`):

```bash
export PYTHONPATH=src
python3 -m bioid_bridge replay \
  --events ../examples/lims-events.example.jsonl \
  --mapping ../examples/lims-mapping.example.json \
  --registry ../examples/wallet-registry.example.json \
  --db .state/bridge.sqlite

python3 -m bioid_bridge history --tube SY00000107 --db .state/bridge.sqlite
python3 -m bioid_bridge inventory --wallet SYN-FRZ-LT80 --db .state/bridge.sqlite
python3 -m bioid_bridge reconcile \
  --inventory ../examples/lims-inventory.example.json \
  --mapping ../examples/lims-mapping.example.json \
  --db .state/bridge.sqlite
```

`.state/` is gitignored. Replay prints how many events were applied, skipped or queued. History prints the parent chain and each operation. Inventory prints tubes with a positive balance in that wallet. Reconcile exits 0 when the books match and 1 when they do not.

The example snapshot is wrong on purpose for `SY00000106`: the LIMS row says `FRZ-LT80`, the ledger has `SYN-FRZ-BIOS`. Expect `mismatches: 1`.

The same mapping is in [`examples/lims-mapping.example.yaml`](../examples/lims-mapping.example.yaml). JSON needs no extra package. YAML needs PyYAML.

## What the feed does

The feed is the concept-note blood sample, on the synthetic wallet registry. A MINT event with `children` is a transform: each child is minted, and only `burn_uL` is burned on the parent. The parent row stays, including at 0 µL. `consumed` of 50 µL from the 200 µL DNA tube leaves 150 µL on the same token.

Two adaptations keep the feed inside the wallet rules. Aliquoting runs in `SYN-PROC-ALIQ` after `to_process`, because intake cannot transform. Shipping runs only after the DNA tube has been stored, because a process wallet cannot ship; the feed then receives that same token back into `SYN-FRZ-LT80`. See the integration guide for the full note.

## Idempotency, batches, retries, review

`MockLedger.apply_batch` writes the new balances and the processed event id in one SQLite transaction. A second replay of the same id does nothing. The batch id is `mock-` plus the SHA-256 of the event ids in that batch, and it is what the bridge stores in a local write-back table under the field name `bioid_tx`. That table stands in for the LIMS column a site would update with a real transaction hash.

Default batch size is 8. If a batch fails a transition rule, the ledger rolls the batch back and the bridge applies the events one by one. Valid events commit. The invalid event is inserted into `review_queue` and is not marked processed.

`fail_next` on the ledger simulates a transient error. The bridge retries up to `--retries` (default 3). A rule violation is not retried. If the retries run out, the event is queued for a person.

## Backends

`LimsBridge` takes a `backend`. The default is the ledger itself: `MockLedger.submit` applies the batch locally. Pass a `TezosBackend` and the same replay calls `submit` there instead. That stub refuses the call, so the ledger stays unchanged.

`MockLedger` keeps tokens, parent links, history and balances in memory or in a SQLite file. No network.

`TezosBackend` is the shape of a later pytezos client. This version does not import pytezos. `from_env` reads:

| Variable | Meaning |
|---|---|
| `TEZOS_NETWORK` | `shadownet`. Ghostnet has been removed. Mainnet is refused |
| `TEZOS_RPC_URL` | That testnet's RPC URL |
| `TEZOS_CONTRACT` | Contract address, empty until `contracts/` has the FA2 contract |
| `TEZOS_KEY_REF` | HSM or cloud KMS alias, such as `kms://alias/syn-custodian-lab` |

A network or RPC URL that indicates mainnet is refused. Ghostnet is refused too: it is no longer a public testnet. `TEZOS_NETWORK` must be `shadownet`, and the RPC URL must be a Shadownet endpoint. A value that looks like a raw secret key (`edsk…` and the other secret prefixes) is refused. `submit` encodes the contract entrypoint and then raises `InjectionRefused`. It does not sign, broadcast, or originate. Copy [`bridge/.env.example`](.env.example) if you want the variable names locally. Do not fill it with a secret. The origination steps are in [`contracts/README.md`](../contracts/README.md).

## Tests

```bash
cd bridge
python3 -m pytest
```

The tests cover mapping, rejection of an illegal transform and of a ship out of a process wallet, idempotent replay, partial-volume burns (50 of 200 left at 150, and 500 of 2000 left at 1500 with the parent still present), and the one deliberate reconciliation mismatch.

## Data

Do not point this bridge at a real LIMS export. The translator will send only the fields it maps, but the safe pattern is still the one in the integration guide: pseudonymous tube codes, location codes, event ids, volumes, and an opaque consent reference. No names, and no table that links a person to that reference.
