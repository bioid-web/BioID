"""EPCIS 2.0 export of a lineage. Structural checks always run; the full GS1 JSON
schema check runs when jsonschema and a local copy of the schema are available
(set BIOID_EPCIS_SCHEMA to its path)."""

import json
import os

import pytest

from bioid_bridge.cli import main
from bioid_bridge.epcis import EPCIS_CONTEXT, EpcisExporter


@pytest.fixture
def loaded(bridge, events, ledger):
    bridge.replay(events)
    bridge.replay([
        {"event_id": "w-1", "type": "withdrawn_destroy", "tube": "SY00000101", "owner": "STUDY-OWNER"},
        {"event_id": "c-1", "type": "destruction_confirmed", "tube": "SY00000106",
         "occurred_at": "2026-11-24T09:15:00+01:00"},
    ])
    return ledger


def test_document_shape(loaded):
    doc = EpcisExporter(loaded, "https://example.org/bioid/").document("SY00000106")
    assert doc["type"] == "EPCISDocument" and doc["schemaVersion"] == "2.0"
    assert doc["@context"][0] == EPCIS_CONTEXT
    events = doc["epcisBody"]["eventList"]
    kinds = [e["type"] for e in events]
    assert kinds[0] == "ObjectEvent" and events[0]["action"] == "ADD"
    transforms = [e for e in events if e["type"] == "TransformationEvent"]
    # aliquot, split, rna_isolation, dna_isolation: one event each, not one per child.
    assert len(transforms) == 4
    first = transforms[0]
    assert first["inputEPCList"] == ["https://example.org/bioid/tube/SY00000101"]
    assert len(first["outputEPCList"]) >= 2
    destroyed = [e for e in events if e.get("bizStep") == "destroying"]
    assert destroyed and destroyed[0]["action"] == "DELETE"
    assert destroyed[0]["eventTime"] == "2026-11-24T09:15:00+01:00"
    assert destroyed[0]["eventTimeZoneOffset"] == "+01:00"
    assert any(e.get("disposition") == "unavailable" for e in events)
    assert len({e["eventID"] for e in events}) == len(events)


def test_no_personal_fields_leak(loaded):
    text = json.dumps(EpcisExporter(loaded).document("SY00000101"))
    assert "cref-" not in text, "consent references stay out of the export"
    assert "STUDY-OWNER" not in text


def test_cli_writes_a_file(loaded, tmp_path, registry):
    db = tmp_path / "ledger.sqlite"
    disk = loaded.conn
    disk.commit()
    target = __import__("sqlite3").connect(db)
    disk.backup(target)
    target.close()
    out = tmp_path / "lineage.jsonld"
    assert main(["export-epcis", "--tube", "SY00000107", "--db", str(db), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["epcisBody"]["eventList"]
    assert main(["export-epcis", "--tube", "SY99999999", "--db", str(db)]) == 2


def test_against_gs1_schema(loaded):
    path = os.environ.get("BIOID_EPCIS_SCHEMA")
    jsonschema = pytest.importorskip("jsonschema")
    if not path or not os.path.exists(path):
        pytest.skip("set BIOID_EPCIS_SCHEMA to a local copy of the GS1 EPCIS 2.0 JSON schema")
    schema = json.load(open(path, encoding="utf-8"))
    doc = EpcisExporter(loaded).document("SY00000101")
    jsonschema.validate(doc, schema, format_checker=jsonschema.FormatChecker())
