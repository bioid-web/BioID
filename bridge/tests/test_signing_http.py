import json
from pathlib import Path

import pytest

from bioid_bridge.model import MainnetRefused
from bioid_bridge.signing_http import (
    SigningService,
    Wallet,
    load_config,
    michelson_ship_or_receive,
)

FIELD = "tz1TCvD465fjpgL7T6dG1nWqxUQntCUipG3F"
TRANSIT = "tz1ew1YTaVQpQv9M2Pj2cgj729z8QqFzJCWT"
LAB = "tz1cL4AwPrqMcp2CWYC3g4g6NBnktPbLBeS2"
CONTRACT = "KT1B2i1w9CjbcUHrGJSPqYRmFiLJa8pXneJ5"


def _write_config(tmp_path: Path, **overrides):
    sessions = {
        "field": {
            "token": "field-token-test",
            "name": "Field operator (synthetic)",
            "org": "Demo field site",
            "alias": "field-custodian",
            "wallet_addresses": [FIELD],
        },
        "lab": {
            "token": "lab-token-test",
            "name": "Lab operator (synthetic)",
            "org": "Demo lab site",
            "alias": "lab-custodian",
            "wallet_addresses": [LAB],
        },
    }
    sessions_path = tmp_path / "bearers.json"
    sessions_path.write_text(json.dumps(sessions))
    data = {
        "network": "shadownet",
        "rpc_url": "https://rpc.shadownet.teztnets.com",
        "chain_id": "NetXsqzbfFenSTS",
        "tzkt_api": "https://api.shadownet.tzkt.io/v1",
        "contract": CONTRACT,
        "client_dir": str(tmp_path),
        "bind": "127.0.0.1",
        "port": 8787,
        "sessions_file": str(sessions_path),
        "idempotency_path": str(tmp_path / "idempotency.json"),
        "wallets": [
            {"address": FIELD, "label": "Field intake (synthetic)", "type": "INTAKE", "site": "field", "custodian": FIELD},
            {"address": TRANSIT, "label": "Courier (synthetic)", "type": "TRANSIT", "site": "courier", "custodian": TRANSIT},
            {"address": LAB, "label": "Lab freezer (synthetic)", "type": "STORAGE", "site": "lab", "custodian": LAB},
        ],
    }
    data.update(overrides)
    path = tmp_path / "service.json"
    path.write_text(json.dumps(data))
    return path


def test_refuses_mainnet_config(tmp_path):
    with pytest.raises(MainnetRefused):
        load_config(_write_config(tmp_path, network="mainnet", rpc_url="https://rpc.tzkt.io/mainnet"))


def test_refuses_non_shadownet_network(tmp_path):
    from bioid_bridge.signing_http import SigningConfigError

    with pytest.raises(SigningConfigError, match="[Ss]hadownet"):
        load_config(_write_config(tmp_path, network="ghostnet", rpc_url="https://rpc.ghostnet.teztnets.com"))


def test_michelson_arg():
    arg = michelson_ship_or_receive("SY00000401", TRANSIT)
    assert 'Pair "SY00000401"' in arg
    assert "None" in arg
    assert TRANSIT in arg
    with pytest.raises(Exception):
        michelson_ship_or_receive("bad;drop", TRANSIT)


def _service(tmp_path, calls=None):
    calls = calls if calls is not None else []

    def injector(alias, entrypoint, arg, dry_run):
        calls.append((alias, entrypoint, arg, dry_run))
        if dry_run:
            return {"fee_mutez": 1500}
        return {"op_hash": "ooSyntheticHash00000000000000000000000000000000001", "fee_mutez": 1500}

    cfg = load_config(_write_config(tmp_path))
    return SigningService(cfg, injector=injector, chain_id_fn=lambda _rpc: "NetXsqzbfFenSTS"), calls


def test_auth_and_me(tmp_path):
    service, _ = _service(tmp_path)
    status, body = service.handle("GET", "/me", {}, b"")
    assert status == 401
    status, body = service.handle("GET", "/me", {"Authorization": "Bearer field-token-test"}, b"")
    assert status == 200
    assert body["name"] == "Field operator (synthetic)"
    assert body["wallets"][0]["type"] == "INTAKE"
    assert body["ship_destinations"][0]["type"] == "TRANSIT"
    assert body["receive_destinations"][0]["type"] == "INTAKE"


def test_ship_preflight_and_idempotent_submit(tmp_path):
    service, calls = _service(tmp_path)
    payload = json.dumps(
        {
            "client_request_id": "req-1",
            "tube_code": "SY00000401",
            "to_wallet": TRANSIT,
        }
    ).encode()
    headers = {"Authorization": "Bearer field-token-test"}
    status, body = service.handle("POST", "/custody/ship/preflight", headers, payload)
    assert status == 200 and body["ok"] is True and body["fee_mutez"] == 1500
    status, body = service.handle("POST", "/custody/ship", headers, payload)
    assert status == 200
    assert body["op_hash"].startswith("ooSynthetic")
    status, again = service.handle("POST", "/custody/ship", headers, payload)
    assert status == 200 and again["op_hash"] == body["op_hash"]
    # first preflight + first submit only; retry hits the store
    assert sum(1 for c in calls if c[3] is False) == 1


def test_ship_to_non_transit_goes_to_review(tmp_path):
    service, calls = _service(tmp_path)
    payload = json.dumps(
        {
            "client_request_id": "req-bad",
            "tube_code": "SY00000401",
            "to_wallet": LAB,
        }
    ).encode()
    status, body = service.handle(
        "POST", "/custody/ship", {"Authorization": "Bearer field-token-test"}, payload
    )
    assert status == 202
    assert body["reasons"]
    assert calls == []


def test_receive_rejects_foreign_wallet(tmp_path):
    service, calls = _service(tmp_path)
    payload = json.dumps(
        {
            "client_request_id": "req-lab",
            "tube_code": "SY00000401",
            "to_wallet": FIELD,
        }
    ).encode()
    status, body = service.handle(
        "POST", "/custody/receive", {"Authorization": "Bearer lab-token-test"}, payload
    )
    assert status == 202
    assert calls == []


def test_live_chain_guard(tmp_path):
    service, _ = _service(tmp_path)
    service.chain_id_fn = lambda _rpc: "NetXdQprcVkpaWU"
    status, body = service.handle(
        "POST",
        "/custody/ship",
        {"Authorization": "Bearer field-token-test"},
        json.dumps({"client_request_id": "x", "tube_code": "SY00000401", "to_wallet": TRANSIT}).encode(),
    )
    assert status == 403
