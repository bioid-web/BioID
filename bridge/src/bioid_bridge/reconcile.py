"""Compare a LIMS inventory snapshot with ledger wallets."""

from __future__ import annotations

from bioid_bridge.ledger import MockLedger
from bioid_bridge.mapping import Mapping
from bioid_bridge.model import Mismatch, ReconcileReport


def reconcile(ledger: MockLedger, mapping: Mapping, inventory: dict) -> ReconcileReport:
    mismatches: list[Mismatch] = []
    matched: list[str] = []
    seen: set[str] = set()
    for row in inventory["rows"]:
        tube = row["tube"]
        seen.add(tube)
        location = row["location"]
        lims_wallet = mapping.wallet_for(location)
        lims_balance = int(row["balance_uL"])
        token = ledger.token(tube)
        if token is None:
            mismatches.append(
                Mismatch(
                    tube=tube,
                    kind="missing_on_ledger",
                    lims_location=location,
                    lims_wallet=lims_wallet,
                    ledger_wallet=None,
                    lims_balance=lims_balance,
                    ledger_balance=None,
                )
            )
            continue
        wallet_ok = token["wallet"] == lims_wallet
        balance_ok = token["balance_ul"] == lims_balance
        if wallet_ok and balance_ok:
            matched.append(tube)
            continue
        if not wallet_ok and not balance_ok:
            kind = "wallet_and_balance"
        elif not wallet_ok:
            kind = "wallet"
        else:
            kind = "balance"
        mismatches.append(
            Mismatch(
                tube=tube,
                kind=kind,
                lims_location=location,
                lims_wallet=lims_wallet,
                ledger_wallet=token["wallet"],
                lims_balance=lims_balance,
                ledger_balance=token["balance_ul"],
            )
        )
    for token in ledger.inventory(positive_only=True):
        if token["tube"] in seen:
            continue
        mismatches.append(
            Mismatch(
                tube=token["tube"],
                kind="missing_in_lims",
                lims_location=None,
                lims_wallet=None,
                ledger_wallet=token["wallet"],
                lims_balance=None,
                ledger_balance=token["balance_ul"],
            )
        )
    return ReconcileReport(mismatches=mismatches, matched=matched)
