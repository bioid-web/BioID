from pathlib import Path

import pytest

from bioid_bridge.ledger import MockLedger
from bioid_bridge.mapping import load_events, load_mapping
from bioid_bridge.registry import load_registry
from bioid_bridge.service import LimsBridge

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def registry():
    return load_registry(ROOT / "examples" / "wallet-registry.example.json")


@pytest.fixture
def mapping():
    return load_mapping(ROOT / "examples" / "lims-mapping.example.json")


@pytest.fixture
def events():
    return load_events(ROOT / "examples" / "lims-events.example.jsonl")


@pytest.fixture
def ledger(registry):
    store = MockLedger(":memory:", registry)
    yield store
    store.close()


@pytest.fixture
def bridge(registry, mapping, ledger):
    return LimsBridge(registry=registry, mapping=mapping, ledger=ledger, batch_size=8, max_retries=3)
