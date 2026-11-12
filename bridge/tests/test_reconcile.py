import json

from bioid_bridge.reconcile import reconcile

from conftest import ROOT


def test_example_snapshot_has_one_wallet_mismatch(bridge, ledger, mapping, events):
    bridge.replay(events)
    document = json.loads(
        (ROOT / "examples" / "lims-inventory.example.json").read_text(encoding="utf-8")
    )
    report = reconcile(ledger, mapping, document)
    assert [item.tube for item in report.mismatches] == ["SY00000106"]
    mismatch = report.mismatches[0]
    assert mismatch.kind == "wallet"
    assert mismatch.lims_wallet == "SYN-FRZ-LT80"
    assert mismatch.ledger_wallet == "SYN-FRZ-BIOS"
    assert mismatch.lims_balance == 100
    assert mismatch.ledger_balance == 100
    assert report.matched == ["SY00000102", "SY00000107"]
    text = report.format()
    assert "mismatches: 1" in text
    assert "SY00000106" in text
    assert "SYN-FRZ-BIOS" in text
