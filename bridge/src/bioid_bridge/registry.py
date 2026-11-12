"""Load a wallet registry document."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bioid_bridge.model import RuleViolation


@dataclass(frozen=True)
class Wallet:
    address: str
    type: str
    label: str
    site: str
    active: bool
    custodian_label: str
    custodian_address: str
    process: str = ""


class Registry:
    def __init__(self, wallets: list[Wallet]):
        self.wallets = wallets
        self.by_label = {wallet.label: wallet for wallet in wallets}

    def get(self, label: str) -> Wallet:
        try:
            return self.by_label[label]
        except KeyError as exc:
            raise RuleViolation(f"wallet {label} is not in the registry") from exc


def load_registry(path: str | Path) -> Registry:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    wallets: list[Wallet] = []
    for row in document["wallets"]:
        custodian = row["custodian"]
        wallets.append(
            Wallet(
                address=row["address"],
                type=row["type"],
                label=row["label"],
                site=row["site"],
                active=bool(row.get("active", True)),
                custodian_label=custodian["label"],
                custodian_address=custodian["address"],
                process=row.get("process") or "",
            )
        )
    return Registry(wallets)
