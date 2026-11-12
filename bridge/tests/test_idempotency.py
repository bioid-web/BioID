def test_example_feed_end_state(bridge, ledger, events):
    report = bridge.replay(events)
    assert report.queued == []
    assert len(report.applied) == len(events)

    assert ledger.token("SY00000102")["balance_ul"] == 1000
    assert ledger.token("SY00000102")["wallet"] == "SYN-FRZ-LT80"
    assert ledger.token("SY00000106")["balance_ul"] == 100
    assert ledger.token("SY00000106")["wallet"] == "SYN-FRZ-BIOS"
    assert ledger.token("SY00000106")["parent_id"] == "SY00000104"
    assert ledger.token("SY00000107")["balance_ul"] == 150
    assert ledger.token("SY00000107")["wallet"] == "SYN-FRZ-LT80"
    assert ledger.token("SY00000107")["parent_id"] == "SY00000105"
    for tube in ("SY00000101", "SY00000103", "SY00000104", "SY00000105"):
        token = ledger.token(tube)
        assert token is not None
        assert token["balance_ul"] == 0
        assert token["root_id"] == "SY00000101"

    lineage = ledger.lineage("SY00000107")
    assert lineage["root_to_tube"] == [
        "SY00000101",
        "SY00000103",
        "SY00000105",
        "SY00000107",
    ]
    reasons = [row["reason"] for row in ledger.history("SY00000107")]
    assert reasons == ["dna_isolation", "moved", "consumed", "stored", "shipped", "received"]


def test_replaying_the_same_events_does_not_apply_twice(bridge, ledger, events):
    first = bridge.replay(events)
    balances = {
        tube: (ledger.token(tube)["balance_ul"], ledger.token(tube)["wallet"])
        for tube in (f"SY0000010{n}" for n in range(1, 8))
    }
    history_rows = sum(len(ledger.history(tube)) for tube in balances)
    second = bridge.replay(events)
    assert second.applied == []
    assert second.skipped == first.applied
    assert second.queued == []
    again = {
        tube: (ledger.token(tube)["balance_ul"], ledger.token(tube)["wallet"])
        for tube in balances
    }
    assert again == balances
    assert sum(len(ledger.history(tube)) for tube in balances) == history_rows
    assert ledger.token("SY00000107")["balance_ul"] == 150


def test_transient_failure_is_retried_once(registry, mapping, ledger):
    from bioid_bridge.service import LimsBridge

    ledger.fail_next(1)
    bridge = LimsBridge(
        registry=registry, mapping=mapping, ledger=ledger, batch_size=4, max_retries=3
    )
    event = {
        "event_id": "retry-1",
        "type": "collected",
        "tube": "SY00000101",
        "volume_uL": 3000,
        "sample_type": "blood",
        "to_location": "COURIER",
    }
    report = bridge.replay([event])
    assert report.applied == ["retry-1"]
    assert report.queued == []
    assert ledger.token("SY00000101")["balance_ul"] == 3000
    assert len(ledger.history("SY00000101")) == 1


def test_exhausted_retries_land_in_the_review_queue(registry, mapping, ledger):
    from bioid_bridge.service import LimsBridge

    ledger.fail_next(5)
    bridge = LimsBridge(
        registry=registry, mapping=mapping, ledger=ledger, batch_size=4, max_retries=3
    )
    event = {
        "event_id": "retry-2",
        "type": "collected",
        "tube": "SY00000101",
        "volume_uL": 500,
        "sample_type": "blood",
        "to_location": "COURIER",
    }
    report = bridge.replay([event])
    assert report.applied == []
    assert report.queued == ["retry-2"]
    assert ledger.token("SY00000101") is None
    assert "transient failure" in ledger.review_queue()[0]["message"]
