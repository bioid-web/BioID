def _primary(event_id, tube, volume, location="COURIER"):
    return {
        "event_id": event_id,
        "type": "collected",
        "tube": tube,
        "volume_uL": volume,
        "sample_type": "blood",
        "to_location": location,
    }


def test_partial_consume_leaves_the_token(bridge, ledger):
    events = [
        _primary("p-1", "SY00000107", 200),
        {
            "event_id": "p-2",
            "type": "received",
            "tube": "SY00000107",
            "to_location": "RECEPTION",
        },
        {
            "event_id": "p-3",
            "type": "to_process",
            "tube": "SY00000107",
            "to_location": "PROC-SEQ",
        },
        {
            "event_id": "p-4",
            "type": "consumed",
            "tube": "SY00000107",
            "burn_uL": 50,
        },
    ]
    report = bridge.replay(events)
    assert report.queued == []
    token = ledger.token("SY00000107")
    assert token["balance_ul"] == 150
    assert token["wallet"] == "SYN-PROC-SEQ"
    burn = ledger.history("SY00000107")[-1]
    assert burn["op"] == "burn"
    assert burn["reason"] == "consumed"
    assert burn["volume_ul"] == 50
    assert burn["balance_after"] == 150


def test_partial_transform_burn_keeps_the_parent(bridge, ledger):
    events = [
        _primary("t-1", "SY00000101", 2000),
        {
            "event_id": "t-2",
            "type": "received",
            "tube": "SY00000101",
            "to_location": "RECEPTION",
        },
        {
            "event_id": "t-3",
            "type": "to_process",
            "tube": "SY00000101",
            "to_location": "PROC-ALIQ",
        },
        {
            "event_id": "t-4",
            "type": "aliquoted",
            "tube": "SY00000101",
            "burn_uL": 500,
            "children": [
                {
                    "tube": "SY00000102",
                    "volume_uL": 500,
                    "sample_type": "aliquot",
                    "to_location": "PROC-ALIQ",
                }
            ],
        },
    ]
    report = bridge.replay(events)
    assert report.queued == []
    parent = ledger.token("SY00000101")
    child = ledger.token("SY00000102")
    assert parent["balance_ul"] == 1500
    assert parent["wallet"] == "SYN-PROC-ALIQ"
    assert child["balance_ul"] == 500
    assert child["parent_id"] == "SY00000101"
    assert child["root_id"] == "SY00000101"
    assert ledger.lineage("SY00000102")["root_to_tube"] == ["SY00000101", "SY00000102"]


def test_adjust_volume_does_not_mint(bridge, ledger):
    events = [
        _primary("a-1", "SY00000101", 3000),
        {
            "event_id": "a-2",
            "type": "received",
            "tube": "SY00000101",
            "to_location": "RECEPTION",
        },
        {
            "event_id": "a-3",
            "type": "measured",
            "tube": "SY00000101",
            "volume_uL": 2900,
        },
    ]
    report = bridge.replay(events)
    assert report.queued == []
    token = ledger.token("SY00000101")
    assert token["balance_ul"] == 2900
    assert token["wallet"] == "SYN-INTAKE"
    assert [row["op"] for row in ledger.history("SY00000101")] == [
        "mint_primary",
        "receive",
        "adjust",
    ]
