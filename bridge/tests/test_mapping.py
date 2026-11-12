from bioid_bridge.mapping import load_mapping, translate

from conftest import ROOT


def test_locations_point_at_registry_labels(mapping, registry):
    assert set(mapping.locations) == {
        "RECEPTION",
        "FRZ-LT80",
        "FRZ-BIOS",
        "PROC-ALIQ",
        "PROC-RNA",
        "PROC-DNA",
        "PROC-SEQ",
        "COURIER",
    }
    for label in mapping.locations.values():
        assert registry.get(label).label == label


def test_event_types_use_the_public_operation_names(mapping):
    expect = {
        "collected": "MINT",
        "received": "RECEIVE",
        "stored": "MOVE",
        "moved": "MOVE",
        "to_process": "MOVE",
        "shipped": "SHIP",
        "aliquoted": "MINT",
        "split": "MINT",
        "rna_isolation": "MINT",
        "dna_isolation": "MINT",
        "consumed": "BURN",
        "measured": "ADJUST",
        "retrieval": "MOVE",
        "data_attached": "DATA",
        "access_requested": "ACCESS_REQUEST",
        "access_approved": "ACCESS_APPROVE",
    }
    for event_type, operation in expect.items():
        assert mapping.spec_for(event_type)["operation"] == operation
        assert mapping.spec_for(event_type)["reason"]


def test_translate_primary_mint_move_and_transform(mapping):
    minted = translate(
        {
            "event_id": "t-mint",
            "type": "collected",
            "tube": "SY00000101",
            "volume_uL": 3000,
            "sample_type": "blood",
            "to_location": "COURIER",
            "owner": "STUDY-OWNER",
            "consent_ref": "cref-a1b2c3",
        },
        mapping,
    )
    assert minted.op == "mint_primary"
    assert minted.reason == "collected"
    assert minted.to_wallet == "SYN-TRANSIT-COURIER"
    assert minted.volume_uL == 3000

    moved = translate(
        {
            "event_id": "t-move",
            "type": "stored",
            "tube": "SY00000102",
            "from_location": "PROC-ALIQ",
            "to_location": "FRZ-LT80",
        },
        mapping,
    )
    assert moved.op == "move"
    assert moved.reason == "stored"
    assert moved.to_wallet == "SYN-FRZ-LT80"

    shipped = translate(
        {
            "event_id": "t-ship",
            "type": "shipped",
            "tube": "SY00000107",
            "to_location": "COURIER",
        },
        mapping,
    )
    assert shipped.op == "ship"
    assert shipped.reason == "shipped"

    aliquot = translate(
        {
            "event_id": "t-aliquot",
            "type": "aliquoted",
            "tube": "SY00000101",
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
        mapping,
    )
    assert aliquot.op == "transform"
    assert aliquot.reason == "aliquoted"
    assert aliquot.burn_uL == 3000
    assert aliquot.children[0].to_wallet == "SYN-PROC-ALIQ"

    burned = translate(
        {"event_id": "t-burn", "type": "consumed", "tube": "SY00000107", "burn_uL": 50},
        mapping,
    )
    assert burned.op == "burn"
    assert burned.reason == "consumed"
    assert burned.burn_uL == 50

    adjusted = translate(
        {
            "event_id": "t-adj",
            "type": "measured",
            "tube": "SY00000101",
            "volume_uL": 2900,
        },
        mapping,
    )
    assert adjusted.op == "adjust"
    assert adjusted.reason == "measured"
    assert adjusted.volume_uL == 2900


def test_yaml_mapping_matches_json():
    yaml_mapping = load_mapping(ROOT / "examples" / "lims-mapping.example.yaml")
    json_mapping = load_mapping(ROOT / "examples" / "lims-mapping.example.json")
    assert yaml_mapping.locations == json_mapping.locations
    assert yaml_mapping.events == json_mapping.events
