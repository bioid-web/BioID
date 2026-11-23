"""Volume conservation (v0.4).

Conservation applies to the source material consumed (the burn from the parent), not to
the liquid volume of the outputs. Plain aliquots and splits add no liquid, so their
children are capped by the burn. Isolation/elution, dilution and titration add buffer or
diluent and may produce more volume than was drawn; they record the transformation type,
the volume consumed and, ideally, the added volume or dilution factor.
"""


def _feed(burn, children, kind, **extra):
    transform = {"event_id": "k-4", "type": kind, "tube": "SY00000301",
                 "from_location": "PROC-ALIQ", "burn_uL": burn,
                 "children": [
                     {"tube": f"SY0000031{i}", "volume_uL": v, "sample_type": "aliquot",
                      "to_location": "PROC-ALIQ"}
                     for i, v in enumerate(children)
                 ]}
    transform.update(extra)
    return [
        {"event_id": "k-1", "type": "collected", "tube": "SY00000301", "volume_uL": 5000,
         "sample_type": "blood", "to_location": "COURIER", "owner": "STUDY-OWNER",
         "consent_ref": "cref-k"},
        {"event_id": "k-2", "type": "received", "tube": "SY00000301",
         "from_location": "COURIER", "to_location": "RECEPTION"},
        {"event_id": "k-3", "type": "to_process", "tube": "SY00000301",
         "from_location": "RECEPTION", "to_location": "PROC-ALIQ"},
        transform,
    ]


def _message(ledger, event_id="k-4"):
    return {r["event_id"]: r["message"] for r in ledger.review_queue()}[event_id]


# Capped: plain aliquot / split of the same material.

def test_aliquot_that_creates_volume_is_refused(bridge, ledger):
    report = bridge.replay(_feed(burn=1000, children=[600, 600], kind="aliquoted"))
    assert "k-4" in report.queued
    assert ledger.token("SY00000310") is None
    assert ledger.token("SY00000301")["balance_ul"] == 5000
    message = _message(ledger)
    assert "1200" in message and "1000" in message


def test_aliquot_with_loss_is_accepted(bridge, ledger):
    report = bridge.replay(_feed(burn=1000, children=[450, 450], kind="aliquoted"))
    assert "k-4" in report.applied
    assert ledger.token("SY00000301")["balance_ul"] == 4000


def test_split_is_capped_by_the_burn(bridge, ledger):
    report = bridge.replay(_feed(burn=1000, children=[1001], kind="split"))
    assert "k-4" in report.queued
    report = bridge.replay(_feed(burn=1000, children=[500, 500], kind="split"))
    assert "k-4" in report.applied


def test_aliquot_that_adds_liquid_is_refused(bridge, ledger):
    # Adding liquid makes it a dilution; it must be recorded as one.
    report = bridge.replay(_feed(burn=100, children=[150], kind="aliquoted", added_uL=100))
    assert "k-4" in report.queued
    assert "dilution" in _message(ledger)


# Not capped by the burn: steps that add buffer or diluent.

def test_extraction_may_exceed_the_volume_drawn(bridge, ledger):
    # 50 uL of plasma eluted into 100 uL of buffer is normal.
    report = bridge.replay(_feed(burn=50, children=[100], kind="dna_isolation"))
    assert "k-4" in report.applied
    assert ledger.token("SY00000310")["balance_ul"] == 100
    assert ledger.token("SY00000301")["balance_ul"] == 4950


def test_extraction_with_recorded_elution_is_capped_by_burn_plus_added(bridge, ledger):
    report = bridge.replay(_feed(burn=50, children=[150], kind="rna_isolation", added_uL=100))
    assert "k-4" in report.applied
    row = [h for h in ledger.history("SY00000301") if h["op"] == "transform"][0]
    assert row["volume_ul"] == 50 and row["added_ul"] == 100 and row["reason"] == "rna_isolation"


def test_extraction_output_above_burn_plus_added_is_refused(bridge, ledger):
    report = bridge.replay(_feed(burn=50, children=[151], kind="dna_isolation", added_uL=100))
    assert "k-4" in report.queued


def test_dilution_produces_more_volume_than_drawn(bridge, ledger):
    # 1:10 dilution: 100 uL consumed plus 900 uL diluent gives 1000 uL.
    report = bridge.replay(_feed(burn=100, children=[1000], kind="dilution", dilution_factor=10))
    assert "k-4" in report.applied
    assert ledger.token("SY00000310")["balance_ul"] == 1000
    assert ledger.token("SY00000301")["balance_ul"] == 4900
    row = [h for h in ledger.history("SY00000301") if h["op"] == "transform"][0]
    assert row["added_ul"] == 900


def test_dilution_must_record_added_volume_or_factor(bridge, ledger):
    report = bridge.replay(_feed(burn=100, children=[1000], kind="dilution"))
    assert "k-4" in report.queued
    assert "dilution_factor" in _message(ledger)


def test_titration_is_capped_by_burn_plus_added(bridge, ledger):
    report = bridge.replay(_feed(burn=100, children=[500, 501], kind="titration", added_uL=900))
    assert "k-4" in report.queued
    report = bridge.replay(_feed(burn=100, children=[500, 500], kind="titration", added_uL=900))
    assert "k-4" in report.applied


def test_source_consumed_is_still_conserved(bridge, ledger):
    # Adding diluent never lets a step consume more source than the parent holds.
    report = bridge.replay(_feed(burn=5001, children=[100], kind="dilution", added_uL=10))
    assert "k-4" in report.queued
    assert "burn exceeds balance" in _message(ledger)


def test_factor_and_added_volume_must_agree(bridge, ledger):
    report = bridge.replay(
        _feed(burn=100, children=[1000], kind="dilution", dilution_factor=10, added_uL=500)
    )
    assert "k-4" in report.queued


def test_evaporation_cannot_raise_volume(bridge, ledger):
    feed = _feed(burn=1000, children=[500], kind="aliquoted")
    feed[-1]["children"][0]["to_location"] = "FRZ-LT80"
    feed += [
        {"event_id": "k-5", "type": "evaporation", "tube": "SY00000310",
         "from_location": "FRZ-LT80", "volume_uL": 600},
        {"event_id": "k-6", "type": "evaporation", "tube": "SY00000310",
         "from_location": "FRZ-LT80", "volume_uL": 480},
        {"event_id": "k-7", "type": "measured", "tube": "SY00000310",
         "from_location": "FRZ-LT80", "volume_uL": 490},
    ]
    bridge.mapping.events["evaporation"] = {"operation": "ADJUST", "reason": "evaporation"}
    report = bridge.replay(feed)
    assert "k-5" in report.queued
    assert "k-6" in report.applied and "k-7" in report.applied
    assert ledger.token("SY00000310")["balance_ul"] == 490
