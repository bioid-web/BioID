import pytest

from bioid_bridge.ledger import MockLedger
from bioid_bridge.mapping import load_events, load_mapping, translate
from bioid_bridge.model import InjectionRefused
from bioid_bridge.registry import load_registry
from bioid_bridge.service import LimsBridge
from bioid_bridge.tezos import TezosBackend

from conftest import ROOT

PILOT = ROOT / "pilot"


def _bridge():
    registry = load_registry(PILOT / "wallet-registry.json")
    mapping = load_mapping(PILOT / "lims-mapping.json")
    ledger = MockLedger(registry=registry)
    return LimsBridge(registry=registry, mapping=mapping, ledger=ledger), ledger, registry, mapping


def test_pilot_feed_reaches_the_external_user():
    bridge, ledger, registry, _mapping = _bridge()
    events = load_events(PILOT / "scenario.events.jsonl")
    report = bridge.replay(events)
    assert report.queued == []
    assert ledger.token("SY00000211")["wallet"] == "SYN-PILOT-LT80"
    assert ledger.token("SY00000211")["balance_ul"] == 1000
    assert ledger.token("SY00000222")["balance_ul"] == 1500
    assert ledger.token("SY00000231")["wallet"] == "SYN-PILOT-LT80-R1"
    assert ledger.token("SY00000231")["balance_ul"] == 2000
    assert ledger.token("SY00000241")["balance_ul"] == 80
    assert ledger.token("SY00000241")["wallet"] == "SYN-PILOT-LT80"
    assert ledger.token("SY00000241")["parent_id"] == "SY00000212"
    assert ledger.token("SY00000201")["balance_ul"] == 0
    kept = ledger.token("SY00000221")
    assert kept["wallet"] == "SYN-PILOT-EXT"
    assert kept["balance_ul"] == 600
    assert ledger.access_status("SY00000221") == "approved"
    uris = {row["data_uri"] for row in ledger.attachments("SY00000201")}
    assert "https://example.org/synthetic/pilot/qc/SY00000201" in uris
    assert "https://example.org/synthetic/pilot/volume/SY00000201" in uris
    assert any(row["data_type"] == "rin" for row in ledger.attachments("SY00000212"))
    assert any(
        row["data_uri"].endswith("example.synthetic.pilot-use")
        for row in ledger.attachments("SY00000221")
    )
    assert registry.get("SYN-PILOT-EXT").type == "EXTERNAL_USER"
    assert registry.get("SYN-PILOT-RETRIEVAL").process == "retrieval"


def test_retrieval_ship_without_approval_is_queued():
    bridge, ledger, _registry, _mapping = _bridge()
    events = [
        {
            "event_id": "pilot-x1",
            "type": "collected",
            "tube": "SY00000221",
            "volume_uL": 1000,
            "sample_type": "aliquot",
            "to_location": "RECEPTION",
            "consent_ref": "cref-pilot-01",
        },
        {
            "event_id": "pilot-x2",
            "type": "to_process",
            "tube": "SY00000221",
            "to_location": "PROC-ALIQ",
        },
        {
            "event_id": "pilot-x3",
            "type": "stored",
            "tube": "SY00000221",
            "to_location": "FRZ-LT80",
        },
        {
            "event_id": "pilot-x4",
            "type": "retrieval",
            "tube": "SY00000221",
            "to_location": "PROC-RETRIEVAL",
        },
        {
            "event_id": "pilot-x5",
            "type": "shipped",
            "tube": "SY00000221",
            "to_location": "COURIER",
        },
    ]
    report = bridge.replay(events)
    assert "pilot-x5" in report.queued
    assert ledger.token("SY00000221")["wallet"] == "SYN-PILOT-RETRIEVAL"
    assert not ledger.is_applied("pilot-x5")


def test_external_use_encodes_as_report_use():
    _bridge_obj, _ledger, registry, mapping = _bridge()
    op = translate(
        {
            "event_id": "pilot-023",
            "type": "consumed",
            "tube": "SY00000221",
            "from_location": "EXT-USER",
            "burn_uL": 400,
        },
        mapping,
    )
    backend = TezosBackend(
        rpc_url="https://rpc.shadownet.teztnets.com",
        contract="KT1SyntheticContractAddressPlaceholder",
        key_ref="kms://alias/syn-pilot-guest",
        network="shadownet",
        registry=registry,
    )
    payload = backend.encode([op])[0]
    assert payload["entrypoint"] == "report_use"
    assert payload["parameter"]["action"] == "consumed"
    assert payload["parameter"]["volume"] == 400
    assert payload["network"] == "shadownet"
    with pytest.raises(InjectionRefused) as caught:
        backend.submit([op])
    assert caught.value.payloads[0]["entrypoint"] == "report_use"
