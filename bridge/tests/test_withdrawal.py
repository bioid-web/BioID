"""Withdrawal, freeze and destruction on the offline ledger.

These mirror the contract: `withdraw` freezes the whole lineage of the root tube,
`confirm_destroyed` burns what is left only after physical destruction is reported,
and a frozen tube refuses custody, volume and access operations.
"""

import pytest

from bioid_bridge.mapping import translate
from bioid_bridge.tezos import TezosBackend

ROOT_TUBE = "SY00000101"
OWNER = "STUDY-OWNER"


def _withdraw(kind="withdrawn_destroy", *, event_id="w-1", tube=ROOT_TUBE, owner=OWNER):
    return {"event_id": event_id, "type": kind, "tube": tube, "owner": owner}


def _lineage(ledger):
    return [t for t in ledger.inventory(positive_only=False) if t["root_id"] == ROOT_TUBE]


@pytest.fixture
def loaded(bridge, events, ledger):
    bridge.replay(events)
    return ledger


def test_withdraw_freezes_every_tube_in_the_lineage(bridge, loaded):
    report = bridge.replay([_withdraw()])
    assert report.queued == []
    members = _lineage(loaded)
    assert len(members) == 7
    assert {t["status"] for t in members} == {"frozen"}
    wallets = {t["wallet"] for t in members}
    assert len(wallets) > 1, "the freeze must reach tubes in different wallets"
    assert loaded.token("SY00000106")["outcome"] == "destroy"


def test_each_tube_gets_a_history_row_for_the_freeze(bridge, loaded):
    bridge.replay([_withdraw()])
    for tube in ("SY00000101", "SY00000106", "SY00000107"):
        ops = [row["op"] for row in loaded.history(tube)]
        assert ops[-1] == "withdraw"


def test_frozen_tube_refuses_custody_volume_and_access(bridge, loaded):
    bridge.replay([_withdraw()])
    attempts = [
        {"event_id": "f-1", "type": "moved", "tube": "SY00000102",
         "from_location": "FRZ-LT80", "to_location": "FRZ-BIOS"},
        {"event_id": "f-2", "type": "measured", "tube": "SY00000106",
         "from_location": "FRZ-BIOS", "volume_uL": 90},
    ]
    report = bridge.replay(attempts)
    assert report.applied == []
    messages = {row["event_id"]: row["message"] for row in loaded.review_queue()}
    assert "frozen" in messages["f-1"]
    assert "frozen" in messages["f-2"]
    assert loaded.token("SY00000106")["balance_ul"] == 100


def test_attach_data_stays_open_on_a_frozen_tube(bridge, loaded):
    bridge.replay([_withdraw()])
    report = bridge.replay([
        {"event_id": "d-1", "type": "data_attached", "tube": "SY00000102",
         "data": {"data_uri": "ipfs://bafysyntheticqcreport", "content_sha256": "a" * 64,
                  "data_type": "QC", "step": "withdrawal-audit"}}
    ])
    assert report.applied == ["d-1"]


def test_withdraw_needs_the_owner_and_the_root(bridge, loaded):
    bridge.replay([
        _withdraw(event_id="w-bad-owner", owner="SOMEONE-ELSE"),
        _withdraw(event_id="w-no-owner", owner=None),
        _withdraw(event_id="w-child", tube="SY00000102"),
    ])
    messages = {row["event_id"]: row["message"] for row in loaded.review_queue()}
    assert "owner" in messages["w-bad-owner"]
    assert "owner" in messages["w-no-owner"]
    assert "root" in messages["w-child"]
    assert loaded.token(ROOT_TUBE)["status"] != "frozen"


def test_a_second_withdrawal_is_refused(bridge, loaded):
    bridge.replay([_withdraw()])
    bridge.replay([_withdraw("withdrawn_stop_use", event_id="w-2")])
    messages = {row["event_id"]: row["message"] for row in loaded.review_queue()}
    assert "already" in messages["w-2"]
    assert loaded.token(ROOT_TUBE)["outcome"] == "destroy"


def test_stop_use_marks_the_lineage_stopped_and_cannot_be_destroyed(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_stop_use")])
    assert {t["status"] for t in _lineage(loaded)} == {"stopped"}
    bridge.replay([{"event_id": "c-1", "type": "destruction_confirmed", "tube": "SY00000102"}])
    assert "frozen" in {r["event_id"]: r["message"] for r in loaded.review_queue()}["c-1"]


def test_confirm_destroyed_burns_the_rest_and_leaves_inventory(bridge, loaded):
    bridge.replay([_withdraw()])
    before = loaded.token("SY00000102")["balance_ul"]
    assert before > 0
    report = bridge.replay([
        {"event_id": "c-1", "type": "destruction_confirmed", "tube": "SY00000102"}
    ])
    assert report.applied == ["c-1"]
    token = loaded.token("SY00000102")
    assert token["balance_ul"] == 0 and token["status"] == "destroyed"
    assert "SY00000102" not in {t["tube"] for t in loaded.inventory()}
    last = loaded.history("SY00000102")[-1]
    assert (last["op"], last["volume_ul"], last["balance_after"]) == ("confirm_destroyed", before, 0)
    # one confirmation per tube: the rest of the lineage is still frozen and still held
    assert loaded.token("SY00000106")["status"] == "frozen"
    assert loaded.token("SY00000106")["balance_ul"] == 100


def test_confirm_destroyed_without_a_withdrawal_is_refused(bridge, loaded):
    report = bridge.replay([
        {"event_id": "c-0", "type": "destruction_confirmed", "tube": "SY00000102"}
    ])
    assert report.applied == []
    assert loaded.token("SY00000102")["balance_ul"] > 0


def test_anonymise_clears_the_consent_link_and_reopens_the_lineage(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_anonymise")])
    bridge.replay([{"event_id": "a-1", "type": "anonymisation_done", "tube": ROOT_TUBE,
                    "owner": OWNER}])
    members = _lineage(loaded)
    assert {t["status"] for t in members} == {"anonymised"}
    assert {t["consent_ref"] for t in members} == {None}
    report = bridge.replay([
        {"event_id": "m-1", "type": "moved", "tube": "SY00000102",
         "from_location": "FRZ-LT80", "to_location": "FRZ-BIOS"}
    ])
    assert report.applied == ["m-1"]


def test_replaying_a_withdrawal_is_idempotent(bridge, loaded):
    bridge.replay([_withdraw()])
    again = bridge.replay([_withdraw()])
    assert again.skipped == ["w-1"]


def test_tezos_backend_encodes_the_withdrawal_entrypoints(mapping, registry):
    backend = TezosBackend(
        rpc_url="https://rpc.shadownet.teztnets.com",
        contract="KT1SyntheticContractAddressPlaceholder",
        key_ref="kms://alias/syn-custodian-lab",
        network="shadownet",
        registry=registry,
    )
    ops = [
        translate(_withdraw(), mapping),
        translate({"event_id": "c", "type": "destruction_confirmed", "tube": "SY00000102"}, mapping),
    ]
    calls = [(p["entrypoint"], p["parameter"]) for p in backend.encode(ops)]
    assert calls == [
        ("withdraw", {"code": ROOT_TUBE, "outcome": "destroy"}),
        ("confirm_destroyed", {"code": "SY00000102"}),
    ]


def test_unfreeze_anonymised_runs_once(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_anonymise")])
    first = bridge.replay([_withdraw("anonymisation_done", event_id="w-2")])
    assert "w-2" in first.applied
    second = bridge.replay([_withdraw("anonymisation_done", event_id="w-3")])
    assert "w-3" in second.queued
