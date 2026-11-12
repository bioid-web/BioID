"""Shared types for the reference bridge."""

from __future__ import annotations

from dataclasses import dataclass


class BridgeError(Exception):
    """Base error for the reference bridge."""


class RuleViolation(BridgeError):
    """The event breaks a wallet-type transition rule."""


class MappingError(BridgeError):
    """The event or the mapping config cannot be translated."""


class TransientChainError(BridgeError):
    """A retryable failure while submitting a batch."""


class MainnetRefused(BridgeError):
    """TezosBackend was pointed at mainnet."""


class ConfigError(BridgeError):
    """Backend configuration is missing or unsafe."""


class ContractNotReady(BridgeError):
    """The FA2 contract this backend would call is not ready to receive a call."""


class InjectionRefused(ContractNotReady):
    """The call was encoded for Shadownet and then not broadcast."""

    def __init__(self, message: str, payloads: list | None = None):
        super().__init__(message)
        self.payloads = [] if payloads is None else payloads


@dataclass(frozen=True)
class DataRef:
    """Off-chain dataset pointer. The URI is not personal data."""

    data_uri: str
    content_hash: str
    data_type: str
    step: str
    licence: str | None = None
    access_level: str | None = None


@dataclass(frozen=True)
class Child:
    tube: str
    volume_uL: int
    sample_type: str | None
    to_wallet: str


@dataclass(frozen=True)
class Operation:
    """One chain operation translated from a single LIMS event."""

    event_id: str
    op: str
    reason: str
    tube: str
    volume_uL: int | None = None
    burn_uL: int | None = None
    to_wallet: str | None = None
    from_wallet: str | None = None
    sample_type: str | None = None
    owner: str | None = None
    consent_ref: str | None = None
    children: tuple[Child, ...] = ()
    data: DataRef | None = None
    agreement_ref: str | None = None
    agreement_hash: str | None = None
    duo_codes: str | None = None
    request_event_id: str | None = None


@dataclass
class Mismatch:
    tube: str
    kind: str
    lims_location: str | None
    lims_wallet: str | None
    ledger_wallet: str | None
    lims_balance: int | None
    ledger_balance: int | None

    def format(self) -> str:
        if self.kind == "missing_on_ledger":
            return (
                f"{self.tube} missing on ledger: LIMS {self.lims_location} "
                f"({self.lims_wallet}) {self.lims_balance} µL"
            )
        if self.kind == "missing_in_lims":
            return (
                f"{self.tube} missing in LIMS: ledger {self.ledger_wallet} "
                f"{self.ledger_balance} µL"
            )
        return (
            f"{self.tube} {self.kind}: LIMS {self.lims_location} "
            f"({self.lims_wallet}) {self.lims_balance} µL, "
            f"ledger {self.ledger_wallet} {self.ledger_balance} µL"
        )


@dataclass
class ReconcileReport:
    mismatches: list[Mismatch]
    matched: list[str]

    def format(self) -> str:
        lines = [f"mismatches: {len(self.mismatches)}", f"matched: {len(self.matched)}"]
        for item in self.mismatches:
            lines.append(f"  {item.format()}")
        for tube in self.matched:
            lines.append(f"  match {tube}")
        return "\n".join(lines)


@dataclass
class ReplayReport:
    applied: list[str]
    skipped: list[str]
    queued: list[str]
    batches: list[str]

    def format(self) -> str:
        lines = [
            f"applied: {len(self.applied)}",
            f"skipped: {len(self.skipped)}",
            f"queued: {len(self.queued)}",
            f"batches: {len(self.batches)}",
        ]
        for batch_id in self.batches:
            lines.append(f"  {batch_id}")
        for event_id in self.queued:
            lines.append(f"  review {event_id}")
        return "\n".join(lines)
