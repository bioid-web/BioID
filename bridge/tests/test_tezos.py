import pytest

from bioid_bridge.mapping import translate
from bioid_bridge.model import ConfigError, InjectionRefused, MainnetRefused
from bioid_bridge.tezos import TezosBackend

_SHADOW = "https://rpc.shadownet.teztnets.com"
_ALIAS = "kms://alias/syn-custodian-lab"
_CONTRACT = "KT1SyntheticContractAddressPlaceholder"


def _backend(**overrides):
    values = {
        "rpc_url": _SHADOW,
        "contract": _CONTRACT,
        "key_ref": _ALIAS,
        "network": "shadownet",
    }
    values.update(overrides)
    return TezosBackend(**values)


def test_refuses_mainnet_network():
    with pytest.raises(MainnetRefused):
        _backend(network="mainnet")


def test_refuses_mainnet_rpc_url():
    with pytest.raises(MainnetRefused):
        _backend(rpc_url="https://rpc.tzkt.io/mainnet")


def test_refuses_retired_ghostnet():
    with pytest.raises(ConfigError, match="shadownet"):
        _backend(network="ghostnet", rpc_url="https://rpc.ghostnet.teztnets.com")


def test_refuses_a_raw_secret():
    with pytest.raises(ConfigError, match="raw secret"):
        _backend(key_ref="edskNotARealKey")


def test_empty_contract_is_refused():
    with pytest.raises(ConfigError, match="TEZOS_CONTRACT"):
        TezosBackend.from_env(
            {
                "TEZOS_RPC_URL": _SHADOW,
                "TEZOS_CONTRACT": "",
                "TEZOS_KEY_REF": _ALIAS,
                "TEZOS_NETWORK": "shadownet",
            }
        )


def test_encode_then_refuse_injection(mapping, registry):
    backend = TezosBackend(
        rpc_url=_SHADOW,
        contract=_CONTRACT,
        key_ref=_ALIAS,
        network="shadownet",
        registry=registry,
    )
    minted = translate(
        {
            "event_id": "enc-1",
            "type": "collected",
            "tube": "SY00000101",
            "volume_uL": 3000,
            "sample_type": "blood",
            "to_location": "RECEPTION",
            "owner": "STUDY-OWNER",
            "consent_ref": "cref-a1b2c3",
        },
        mapping,
    )
    moved = translate(
        {
            "event_id": "enc-2",
            "type": "consumed",
            "tube": "SY00000107",
            "burn_uL": 50,
            "from_location": "PROC-SEQ",
        },
        mapping,
    )
    payloads = backend.encode([minted, moved])
    assert payloads[0]["entrypoint"] == "mint_primary"
    assert payloads[0]["parameter"]["to_wallet"] == registry.get("SYN-INTAKE").address
    assert payloads[0]["parameter"]["code"] == "SY00000101"
    assert payloads[1]["entrypoint"] == "consume"
    assert "pytezos" not in payloads[0]
    with pytest.raises(InjectionRefused) as caught:
        backend.submit([minted])
    assert caught.value.payloads[0]["entrypoint"] == "mint_primary"


def test_bridge_submit_does_not_write_the_ledger(registry, mapping, ledger):
    from bioid_bridge.service import LimsBridge

    backend = TezosBackend(
        rpc_url=_SHADOW,
        contract=_CONTRACT,
        key_ref=_ALIAS,
        network="shadownet",
        registry=registry,
    )
    bridge = LimsBridge(registry=registry, mapping=mapping, ledger=ledger, backend=backend)
    event = {
        "event_id": "chain-1",
        "type": "collected",
        "tube": "SY00000101",
        "volume_uL": 3000,
        "sample_type": "blood",
        "to_location": "COURIER",
    }
    with pytest.raises(InjectionRefused):
        bridge.replay([event])
    assert ledger.token("SY00000101") is None
    assert not ledger.is_applied("chain-1")


def test_module_does_not_import_pytezos():
    import bioid_bridge.tezos as tezos

    assert "pytezos" not in tezos.__dict__
