def test_transform_on_intake_is_queued_and_not_applied(bridge, ledger):
    events = [
        {
            "event_id": "bad-1",
            "type": "collected",
            "tube": "SY00000101",
            "volume_uL": 3000,
            "sample_type": "blood",
            "to_location": "COURIER",
        },
        {
            "event_id": "bad-2",
            "type": "received",
            "tube": "SY00000101",
            "from_location": "COURIER",
            "to_location": "RECEPTION",
        },
        {
            "event_id": "bad-3",
            "type": "aliquoted",
            "tube": "SY00000101",
            "from_location": "RECEPTION",
            "burn_uL": 3000,
            "children": [
                {
                    "tube": "SY00000102",
                    "volume_uL": 1000,
                    "sample_type": "aliquot",
                    "to_location": "PROC-ALIQ",
                }
            ],
        },
    ]
    report = bridge.replay(events)
    token = ledger.token("SY00000101")
    assert token["wallet"] == "SYN-INTAKE"
    assert token["balance_ul"] == 3000
    assert ledger.token("SY00000102") is None
    assert "bad-3" in report.queued
    assert "bad-3" not in report.applied
    assert not ledger.is_applied("bad-3")
    queued = {row["event_id"]: row["message"] for row in ledger.review_queue()}
    assert "transform only runs in PROCESS" in queued["bad-3"]
    again = bridge.replay(events)
    assert again.skipped == ["bad-1", "bad-2"]
    assert "bad-3" in again.queued
    assert len(ledger.review_queue()) == 1


def test_ship_from_process_is_queued(bridge, ledger):
    events = [
        {
            "event_id": "ship-1",
            "type": "collected",
            "tube": "SY00000107",
            "volume_uL": 200,
            "sample_type": "DNA",
            "to_location": "COURIER",
        },
        {
            "event_id": "ship-2",
            "type": "received",
            "tube": "SY00000107",
            "to_location": "RECEPTION",
        },
        {
            "event_id": "ship-3",
            "type": "to_process",
            "tube": "SY00000107",
            "to_location": "PROC-SEQ",
        },
        {
            "event_id": "ship-4",
            "type": "shipped",
            "tube": "SY00000107",
            "from_location": "PROC-SEQ",
            "to_location": "COURIER",
        },
    ]
    report = bridge.replay(events)
    token = ledger.token("SY00000107")
    assert token["wallet"] == "SYN-PROC-SEQ"
    assert token["balance_ul"] == 200
    assert "ship-4" in report.queued
    assert not ledger.is_applied("ship-4")
    message = ledger.review_queue()[0]["message"]
    assert "PROCESS to TRANSIT" in message


def test_invalid_event_does_not_block_a_later_valid_one(bridge, ledger):
    events = [
        {
            "event_id": "mix-1",
            "type": "collected",
            "tube": "SY00000101",
            "volume_uL": 1000,
            "sample_type": "blood",
            "to_location": "COURIER",
        },
        {
            "event_id": "mix-2",
            "type": "aliquoted",
            "tube": "SY00000101",
            "burn_uL": 1000,
            "children": [
                {
                    "tube": "SY00000102",
                    "volume_uL": 1000,
                    "sample_type": "aliquot",
                    "to_location": "PROC-ALIQ",
                }
            ],
        },
        {
            "event_id": "mix-3",
            "type": "received",
            "tube": "SY00000101",
            "from_location": "COURIER",
            "to_location": "RECEPTION",
        },
    ]
    report = bridge.replay(events)
    assert report.applied == ["mix-1", "mix-3"]
    assert report.queued == ["mix-2"]
    assert ledger.token("SY00000101")["wallet"] == "SYN-INTAKE"
    assert ledger.token("SY00000102") is None
