"""Shadownet encoder for the bioid FA2 contract.

This module does not import a Tezos client SDK. It builds the entrypoint
parameters the contract in ``contracts/bioid_fa2.py`` expects, then refuses
to sign or broadcast them. Deployment is a separate step the operator runs.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from bioid_bridge.model import (
    ConfigError,
    InjectionRefused,
    MainnetRefused,
    Operation,
)
from bioid_bridge.registry import Registry

_MAINNET_MARKERS = (
    "mainnet",
    "rpc.tzbeta.net",
    "mainnet.api.tez.ie",
)
_SECRET_PREFIXES = ("edsk", "spsk", "p2sk", "edesk")
_SHADOW_RPC = "https://rpc.shadownet.teztnets.com"


class TezosBackend:
    """Read the Shadownet RPC, contract address and a KMS key reference.

    ``encode`` names the contract entrypoint and a JSON parameter.
    ``submit`` encodes, then raises ``InjectionRefused``. It does not sign,
    broadcast, deploy, or call a faucet.
    """

    def __init__(
        self,
        *,
        rpc_url: str,
        contract: str,
        key_ref: str,
        network: str,
        registry: Registry | None = None,
    ):
        self.rpc_url = rpc_url.strip()
        self.contract = contract.strip()
        self.key_ref = key_ref.strip()
        self.network = network.strip()
        self.registry = registry
        self._guard()

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        registry: Registry | None = None,
    ) -> TezosBackend:
        source = env if env is not None else os.environ
        return cls(
            rpc_url=source.get("TEZOS_RPC_URL", ""),
            contract=source.get("TEZOS_CONTRACT", ""),
            key_ref=source.get("TEZOS_KEY_REF", ""),
            network=source.get("TEZOS_NETWORK", ""),
            registry=registry,
        )

    def _guard(self) -> None:
        network = self.network.lower()
        rpc = self.rpc_url.lower()
        if network == "mainnet" or any(marker in rpc for marker in _MAINNET_MARKERS):
            raise MainnetRefused(
                "TezosBackend refuses mainnet. Set TEZOS_NETWORK=shadownet "
                f"and TEZOS_RPC_URL={_SHADOW_RPC}."
            )
        if network == "ghostnet" or "ghostnet" in rpc:
            raise ConfigError(
                "Ghostnet has been removed. Set TEZOS_NETWORK=shadownet "
                f"and TEZOS_RPC_URL={_SHADOW_RPC}."
            )
        if network != "shadownet":
            raise ConfigError("TEZOS_NETWORK must be shadownet")
        if "shadownet" not in rpc:
            raise ConfigError(f"TEZOS_RPC_URL must be a shadownet endpoint, for example {_SHADOW_RPC}")
        if not self.key_ref:
            raise ConfigError("TEZOS_KEY_REF is required")
        lowered = self.key_ref.lower()
        if lowered.startswith(_SECRET_PREFIXES) or "edsk" in lowered:
            raise ConfigError(
                "TEZOS_KEY_REF must be an HSM or cloud KMS alias, such as "
                "kms://alias/syn-custodian-lab. A raw secret key is refused."
            )
        if not self.contract:
            raise ConfigError(
                "TEZOS_CONTRACT is required. Originate on Shadownet with "
                "contracts/deploy/originate.sh, then put the KT1 address here."
            )

    def encode(self, ops: list[Operation]) -> list[dict]:
        """Entrypoint name and parameter for each operation. Nothing is sent."""
        self._guard()
        return [self._one(op) for op in ops]

    def submit(self, ops: list[Operation]) -> str:
        payloads = self.encode(ops)
        raise InjectionRefused(
            "TezosBackend encoded the call and refused to broadcast it. "
            "Origination and injection stay with the operator.",
            payloads,
        )

    def _address(self, label: str | None) -> str | None:
        if label is None:
            return None
        if self.registry is None:
            return label
        return self.registry.get(label).address

    def _one(self, op: Operation) -> dict:
        entrypoint, parameter = self._entrypoint(op)
        return {
            "network": "shadownet",
            "rpc_url": self.rpc_url,
            "contract": self.contract,
            "key_ref": self.key_ref,
            "entrypoint": entrypoint,
            "parameter": parameter,
        }

    def _entrypoint(self, op: Operation) -> tuple[str, dict]:
        if op.op == "mint_primary":
            return "mint_primary", {
                "code": op.tube,
                "to_wallet": self._address(op.to_wallet),
                "volume_ul": op.volume_uL,
                "sample_type": op.sample_type,
                "owner": op.owner,
                "consent_ref": op.consent_ref,
                "reason": op.reason,
            }
        if op.op == "move":
            return "move", {
                "code": op.tube,
                "to_wallet": self._address(op.to_wallet),
                "reason": op.reason,
                "data": _data(op),
            }
        if op.op == "ship":
            return "ship", {
                "code": op.tube,
                "to_wallet": self._address(op.to_wallet),
                "data": _data(op),
            }
        if op.op == "receive":
            return "receive", {
                "code": op.tube,
                "to_wallet": self._address(op.to_wallet),
                "data": _data(op),
            }
        if op.op == "transform":
            return "transform", {
                "code": op.tube,
                "burn_ul": op.burn_uL,
                "reason": op.reason,
                "children": [
                    {
                        "code": child.tube,
                        "volume_ul": child.volume_uL,
                        "sample_type": child.sample_type,
                        "to_wallet": self._address(child.to_wallet),
                    }
                    for child in op.children
                ],
                "data": _data(op),
            }
        if op.op == "burn" and op.reason == "consumed":
            if self._source_type(op) == "EXTERNAL_USER":
                return "report_use", {
                    "code": op.tube,
                    "action": "consumed",
                    "volume": op.burn_uL,
                    "data": _data(op),
                }
            return "consume", {
                "code": op.tube,
                "amount": op.burn_uL,
                "data": _data(op),
            }
        if op.op == "burn" and op.reason == "discarded" and self._source_type(op) == "EXTERNAL_USER":
            return "report_use", {
                "code": op.tube,
                "action": "destroyed",
                "data": _data(op),
            }
        if op.op == "adjust":
            return "adjust_volume", {
                "code": op.tube,
                "volume_ul": op.volume_uL,
                "reason": op.reason,
            }
        if op.op == "attach_data":
            return "attach_data", {"code": op.tube, "data": _data(op)}
        if op.op == "access_request":
            return "request_access", {
                "code": op.tube,
                "agreement_ref": op.agreement_ref,
                "agreement_hash": op.agreement_hash,
                "duo_codes": op.duo_codes,
            }
        if op.op == "access_approve":
            return "approve_access", {
                "code": op.tube,
                "request_event_id": op.request_event_id,
                "note": (
                    "The contract argument is the nat request_id from "
                    "request_access. This encoder does not inject, so it keeps "
                    "the LIMS request event id for the operator to substitute."
                ),
            }
        raise ConfigError(f"no contract entrypoint for {op.op}")

    def _source_type(self, op: Operation) -> str:
        if op.from_wallet is None or self.registry is None:
            return ""
        return self.registry.get(op.from_wallet).type


def _data(op: Operation) -> dict | None:
    if op.data is None:
        return None
    return {
        "data_uri": op.data.data_uri,
        "content_sha256": op.data.content_hash,
        "data_type": op.data.data_type,
        "step": op.data.step,
        "licence": op.data.licence,
        "access_level": op.data.access_level,
    }
