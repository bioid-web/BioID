"""v0.4 lifecycle on the offline ledger: stop_use escalation and an explicit
lineage depth. These mirror contracts/proposals/v0.4-lifecycle.patch."""

import pytest

from bioid_bridge.mapping import translate
from bioid_bridge.model import ConfigError
from bioid_bridge.rules import MAX_GENERATIONS
from bioid_bridge.tezos import TezosBackend

ROOT_TUBE = "SY00000101"
OWNER = "STUDY-OWNER"


def _messages(ledger):
    return {row["event_id"]: row["message"] for row in ledger.review_queue()}


def _lineage(ledger, root=ROOT_TUBE):
    return [t for t in ledger.inventory(positive_only=False) if t["root_id"] == root]


@pytest.fixture
def loaded(bridge, events, ledger):
    bridge.replay(events)
    return ledger


def _withdraw(kind, event_id, owner=OWNER):
    return {"event_id": event_id, "type": kind, "tube": ROOT_TUBE, "owner": owner}


def test_stop_use_can_be_escalated_to_destroy(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_stop_use", "w-1")])
    assert {t["status"] for t in _lineage(loaded)} == {"stopped"}
    report = bridge.replay([_withdraw("withdrawn_destroy", "w-2")])
    assert report.queued == []
    assert {t["status"] for t in _lineage(loaded)} == {"frozen"}
    assert loaded.token("SY00000106")["outcome"] == "destroy"
    bridge.replay([{"event_id": "c-1", "type": "destruction_confirmed", "tube": "SY00000106"}])
    assert loaded.token("SY00000106")["status"] == "destroyed"


def test_stop_use_can_be_escalated_to_anonymise(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_stop_use", "w-1"), _withdraw("withdrawn_anonymise", "w-2")])
    assert loaded.token(ROOT_TUBE)["outcome"] == "anonymise"
    assert {t["status"] for t in _lineage(loaded)} == {"frozen"}


@pytest.mark.parametrize(
    "first, second",
    [
        ("withdrawn_stop_use", "withdrawn_stop_use"),
        ("withdrawn_destroy", "withdrawn_anonymise"),
        ("withdrawn_destroy", "withdrawn_stop_use"),
        ("withdrawn_anonymise", "withdrawn_destroy"),
    ],
)
def test_only_stop_use_escalates(bridge, loaded, first, second):
    bridge.replay([_withdraw(first, "w-1"), _withdraw(second, "w-2")])
    assert "already" in _messages(loaded)["w-2"]


def test_escalation_keeps_destroyed_tubes_destroyed(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_destroy", "w-1")])
    bridge.replay([{"event_id": "c-1", "type": "destruction_confirmed", "tube": "SY00000106"}])
    # A later escalation path cannot exist from destroy, but stop_use -> destroy on a
    # lineage with a destroyed tube must not revive it either.
    assert loaded.token("SY00000106")["status"] == "destroyed"


def test_escalation_needs_the_owner(bridge, loaded):
    bridge.replay([_withdraw("withdrawn_stop_use", "w-1"), _withdraw("withdrawn_destroy", "w-2", "SOMEONE")])
    assert "owner" in _messages(loaded)["w-2"]
    assert loaded.token(ROOT_TUBE)["outcome"] == "stop_use"


def _chain_events(generations):
    events = [
        {"event_id": "d-0", "type": "collected", "tube": "SY00000900", "volume_uL": 5000,
         "sample_type": "blood", "to_location": "COURIER", "owner": OWNER, "consent_ref": "cref-d"},
        {"event_id": "d-1", "type": "received", "tube": "SY00000900", "from_location": "COURIER",
         "to_location": "RECEPTION"},
        {"event_id": "d-2", "type": "to_process", "tube": "SY00000900", "from_location": "RECEPTION",
         "to_location": "PROC-ALIQ"},
    ]
    parent = "SY00000900"
    volume = 1000
    for gen in range(1, generations + 1):
        child = f"SY0000090{gen}"
        events.append({
            "event_id": f"d-g{gen}", "type": "aliquoted", "tube": parent, "from_location": "PROC-ALIQ",
            "burn_uL": volume, "children": [{"tube": child, "volume_uL": volume - 10,
                                             "sample_type": "aliquot", "to_location": "PROC-ALIQ"}],
        })
        parent, volume = child, volume - 20
    return events


def test_lineage_depth_is_explicit(bridge, ledger):
    assert MAX_GENERATIONS == 8
    bridge.replay(_chain_events(MAX_GENERATIONS - 1))
    assert ledger.token("SY00000907")["depth"] == 7
    assert ledger.review_queue() == []
    bridge.replay(_chain_events(MAX_GENERATIONS))
    message = _messages(ledger)["d-g8"]
    assert "8 generations" in message
    assert ledger.token("SY00000908") is None


def test_tezos_v04_encodes_added_ul(mapping, registry):
    common = dict(rpc_url="https://rpc.shadownet.teztnets.com", contract="KT1SyntheticContractAddressPlaceholder",
                  key_ref="kms://alias/syn-custodian-lab", network="shadownet", registry=registry)
    dilution = translate({"event_id": "x-1", "type": "dilution", "tube": "SY00000106",
                          "from_location": "PROC-RNA", "burn_uL": 10, "added_uL": 90,
                          "children": [{"tube": "SY00000199", "volume_uL": 100, "to_location": "PROC-RNA"}]},
                         mapping)
    aliquot = translate({"event_id": "x-2", "type": "aliquoted", "tube": "SY00000106",
                         "from_location": "PROC-RNA", "burn_uL": 10,
                         "children": [{"tube": "SY00000198", "volume_uL": 10, "to_location": "PROC-RNA"}]},
                        mapping)
    deployed = TezosBackend(**common)
    assert "added_ul" not in deployed.encode([dilution])[0]["parameter"]
    proposal = TezosBackend(**common, contract_version="v0.4")
    assert proposal.encode([dilution])[0]["parameter"]["added_ul"] == 90
    assert proposal.encode([aliquot])[0]["parameter"]["added_ul"] is None
    with pytest.raises(ConfigError, match="TEZOS_CONTRACT_VERSION"):
        TezosBackend(**common, contract_version="v9")
    env = dict(TEZOS_RPC_URL=common["rpc_url"], TEZOS_CONTRACT=common["contract"],
               TEZOS_KEY_REF=common["key_ref"], TEZOS_NETWORK="shadownet", TEZOS_CONTRACT_VERSION="v0.4")
    assert TezosBackend.from_env(env).contract_version == "v0.4"
