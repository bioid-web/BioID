"""Wallet-type transition checks from docs/wallet-types.md."""

from __future__ import annotations

from bioid_bridge.model import Operation, RuleViolation
from bioid_bridge.registry import Registry, Wallet

# (source type, destination type) -> allowed move reasons.
# `shipped` may cross sites. Every other reason requires the same site.
_MOVES: dict[tuple[str, str], frozenset[str]] = {
    ("INTAKE", "STORAGE"): frozenset({"stored"}),
    ("INTAKE", "PROCESS"): frozenset({"to_process"}),
    ("INTAKE", "QUARANTINE"): frozenset({"qc_hold"}),
    ("INTAKE", "TRANSIT"): frozenset({"shipped"}),
    ("STORAGE", "STORAGE"): frozenset({"stored", "moved", "thawed"}),
    ("STORAGE", "PROCESS"): frozenset({"to_process", "retrieval"}),
    ("STORAGE", "QUARANTINE"): frozenset({"qc_hold"}),
    ("STORAGE", "TRANSIT"): frozenset({"shipped"}),
    ("PROCESS", "PROCESS"): frozenset({"moved"}),
    ("PROCESS", "STORAGE"): frozenset({"stored"}),
    ("PROCESS", "QUARANTINE"): frozenset({"qc_hold"}),
    ("QUARANTINE", "STORAGE"): frozenset({"released"}),
    ("QUARANTINE", "INTAKE"): frozenset({"released"}),
    ("QUARANTINE", "TRANSIT"): frozenset({"shipped"}),
}

_TRANSFORM_REASONS = frozenset(
    {"aliquoted", "split", "rna_isolation", "dna_isolation", "dilution", "titration"}
)
# Conservation applies to the source material consumed (burn_uL), not to the liquid
# volume of the outputs. A plain aliquot or split of the same material adds no liquid,
# so its children cannot hold more than was drawn.
_CONSERVING_REASONS = frozenset({"aliquoted", "split"})
# Steps that add buffer or diluent (isolation with elution, dilution, titration) may
# produce more volume than was drawn. When the added volume is recorded, outputs are
# capped by burn_uL + added_uL. Dilution and titration must record it.
_ADDING_REASONS = frozenset({"rna_isolation", "dna_isolation", "dilution", "titration"})
_ADDED_REQUIRED = frozenset({"dilution", "titration"})
_WITHDRAW_OUTCOMES = frozenset({"destroy", "anonymise", "stop_use"})
# stop_use may later be made stricter. Nothing else changes once recorded.
_ESCALATIONS = frozenset({"destroy", "anonymise"})
# Generations in one lineage, root included. Matches range(0, 8) in the contract's
# lineage_uris and lineage_has views and the BIOID_DEPTH check in the v0.4 proposal.
MAX_GENERATIONS = 8
# Statuses in which custody, volume and access operations are refused. Mirrors
# p_assert_operable in contracts/bioid_fa2.py. attach_data stays open, as in the contract.
_NOT_OPERABLE = frozenset({"frozen", "stopped", "destroyed"})
_ADJUST_REASONS = frozenset({"measured", "evaporation", "dead_volume"})


def _wallet(registry: Registry, label: str | None, *, inbound: bool) -> Wallet:
    if not label:
        raise RuleViolation("missing wallet")
    wallet = registry.get(label)
    if inbound and not wallet.active:
        raise RuleViolation(f"wallet {label} is inactive")
    return wallet


def _same_place(op: Operation, token: dict) -> None:
    if op.to_wallet and op.to_wallet != token["wallet"]:
        raise RuleViolation(f"{op.op} does not move a tube")
    if op.from_wallet and op.from_wallet != token["wallet"]:
        raise RuleViolation(f"{op.tube} is in {token['wallet']}, not {op.from_wallet}")


def validate(op: Operation, token: dict | None, registry: Registry) -> None:
    """Reject an operation the wallet-type matrix does not allow.

    `token` is the current ledger row, or None when the tube has not been minted.
    """

    if op.op == "mint_primary":
        if token is not None:
            raise RuleViolation(f"{op.tube} already exists")
        dest = _wallet(registry, op.to_wallet, inbound=True)
        if dest.type not in {"INTAKE", "TRANSIT"}:
            raise RuleViolation("mint_primary only lands in INTAKE or TRANSIT")
        if op.reason != "collected":
            raise RuleViolation("mint_primary uses reason collected")
        if op.volume_uL is None or op.volume_uL <= 0:
            raise RuleViolation("mint volume must be a positive integer")
        return

    if token is None:
        raise RuleViolation(f"unknown tube {op.tube}")

    if op.op == "withdraw":
        if token["parent_id"]:
            raise RuleViolation("withdraw is recorded on the root tube")
        if op.reason not in _WITHDRAW_OUTCOMES:
            raise RuleViolation(f"unknown withdrawal outcome {op.reason}")
        previous = token.get("outcome")
        escalation = previous == "stop_use" and op.reason in _ESCALATIONS
        if previous and not escalation:
            # Only stop_use may later be escalated to destroy or anonymise.
            raise RuleViolation(f"{op.tube} already has a withdrawal outcome ({previous})")
        if not escalation and token["status"] in _NOT_OPERABLE:
            raise RuleViolation(f"{op.tube} is already {token['status']}")
        if not op.owner or op.owner != token["owner"]:
            raise RuleViolation("withdraw must be signed by the owner of the root tube")
        return

    if op.op == "confirm_destroyed":
        if token["status"] != "frozen" or token.get("outcome") != "destroy":
            raise RuleViolation("confirm_destroyed needs a lineage frozen with outcome destroy")
        return

    if op.op == "unfreeze_anonymised":
        if token["parent_id"]:
            raise RuleViolation("unfreeze_anonymised is recorded on the root tube")
        if token.get("outcome") != "anonymise":
            raise RuleViolation("unfreeze_anonymised needs outcome anonymise")
        if token["status"] != "frozen":
            raise RuleViolation(f"{op.tube} is {token['status']}, not frozen")
        if not op.owner or op.owner != token["owner"]:
            raise RuleViolation("unfreeze_anonymised must be signed by the owner")
        return

    if op.op != "attach_data" and token["status"] in _NOT_OPERABLE:
        raise RuleViolation(f"{op.tube} is {token['status']}")

    if op.from_wallet and op.from_wallet != token["wallet"]:
        raise RuleViolation(f"{op.tube} is in {token['wallet']}, not {op.from_wallet}")

    source = _wallet(registry, token["wallet"], inbound=False)

    if op.op in {"move", "ship"}:
        dest = _wallet(registry, op.to_wallet, inbound=True)
        if dest.label == source.label:
            raise RuleViolation(f"{op.tube} is already in {dest.label}")
        reason = "shipped" if op.op == "ship" else op.reason
        if op.op == "ship" and op.reason != "shipped":
            raise RuleViolation("ship uses reason shipped")
        if op.op == "ship" and source.type == "PROCESS":
            if source.process != "retrieval" or dest.type != "TRANSIT" or reason != "shipped":
                raise RuleViolation(
                    f"{source.type} to {dest.type} does not allow {reason}"
                )
            return
        allowed = _MOVES.get((source.type, dest.type))
        if not allowed or reason not in allowed:
            raise RuleViolation(
                f"{source.type} to {dest.type} does not allow {reason}"
            )
        if reason != "shipped" and source.site != dest.site:
            raise RuleViolation(f"{reason} stays on one site")
        return

    if op.op == "receive":
        if source.type != "TRANSIT":
            raise RuleViolation("receive only leaves TRANSIT")
        dest = _wallet(registry, op.to_wallet, inbound=True)
        if dest.type not in {"STORAGE", "INTAKE", "QUARANTINE", "EXTERNAL_USER"}:
            raise RuleViolation(
                "receive only lands in STORAGE, INTAKE, QUARANTINE or EXTERNAL_USER"
            )
        if op.reason != "received":
            raise RuleViolation("receive uses reason received")
        return

    if op.op == "transform":
        if source.type != "PROCESS":
            raise RuleViolation("transform only runs in PROCESS")
        if op.reason not in _TRANSFORM_REASONS:
            raise RuleViolation(f"unknown transform reason {op.reason}")
        if op.burn_uL is None or op.burn_uL <= 0:
            raise RuleViolation("transform burns a positive volume")
        if op.burn_uL > token["balance_ul"]:
            raise RuleViolation("burn exceeds balance")
        if not op.children:
            raise RuleViolation("transform mints at least one child")
        if token.get("depth", 0) + 1 >= MAX_GENERATIONS:
            # The contract's lineage views walk MAX_GENERATIONS tubes, root included.
            # Refuse a deeper tube rather than let the views stop without saying so.
            raise RuleViolation(
                f"{op.tube} is generation {token.get('depth', 0)}; lineages stop at "
                f"{MAX_GENERATIONS} generations (root included). Start a new root with a "
                "recorded link instead"
            )
        _same_place(op, token)
        for child in op.children:
            if child.volume_uL <= 0:
                raise RuleViolation("child volume must be a positive integer")
        total = sum(child.volume_uL for child in op.children)
        if op.reason in _CONSERVING_REASONS:
            if op.added_uL is not None:
                raise RuleViolation(
                    f"{op.reason} adds no liquid; record a dilution or isolation instead"
                )
            if total > op.burn_uL:
                raise RuleViolation(
                    f"{op.reason} children hold {total} uL but only {op.burn_uL} uL was drawn"
                )
        elif op.reason in _ADDING_REASONS:
            if op.reason in _ADDED_REQUIRED and op.added_uL is None:
                raise RuleViolation(f"{op.reason} must record added_uL or dilution_factor")
            if op.added_uL is not None and total > op.burn_uL + op.added_uL:
                raise RuleViolation(
                    f"{op.reason} children hold {total} uL but only {op.burn_uL} uL drawn "
                    f"plus {op.added_uL} uL added"
                )
        for child in op.children:
            dest = _wallet(registry, child.to_wallet, inbound=True)
            if dest.type not in {"STORAGE", "PROCESS"}:
                raise RuleViolation("transform output is STORAGE or PROCESS")
            if dest.site != source.site:
                raise RuleViolation("transform output stays on the process site")
        return

    if op.op == "burn":
        _same_place(op, token)
        if op.reason == "consumed" and source.type not in {"PROCESS", "EXTERNAL_USER"}:
            raise RuleViolation("consumed only runs in PROCESS or EXTERNAL_USER")
        if op.reason == "discarded" and source.type not in {
            "PROCESS",
            "INTAKE",
            "QUARANTINE",
            "EXTERNAL_USER",
        }:
            raise RuleViolation("discarded is not allowed in this wallet")
        if op.reason not in {"consumed", "discarded", "lost"}:
            raise RuleViolation(f"burn reason {op.reason} is outside this bridge")
        if op.burn_uL is None or op.burn_uL <= 0:
            raise RuleViolation("burn volume must be a positive integer")
        if op.burn_uL > token["balance_ul"]:
            raise RuleViolation("burn exceeds balance")
        return

    if op.op == "adjust":
        _same_place(op, token)
        if source.type not in {"INTAKE", "STORAGE"}:
            raise RuleViolation("adjust_volume only runs on INTAKE and STORAGE")
        if op.reason not in _ADJUST_REASONS:
            raise RuleViolation(f"unknown adjust reason {op.reason}")
        if op.volume_uL is None or op.volume_uL < 0:
            raise RuleViolation("adjusted volume must be zero or a positive integer")
        if op.reason != "measured" and op.volume_uL > token["balance_ul"]:
            raise RuleViolation(f"{op.reason} can only lower the volume; use measured")
        return

    if op.op == "attach_data":
        _check_data(op.data)
        return

    if op.op == "access_request":
        if not op.agreement_ref or not op.agreement_hash or not op.duo_codes:
            raise RuleViolation("access request needs an agreement reference, hash and DUO codes")
        _check_hash(op.agreement_hash)
        return

    if op.op == "access_approve":
        if not op.request_event_id:
            raise RuleViolation("access approval names the request event")
        return

    raise RuleViolation(f"unknown operation {op.op}")


def _check_hash(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise RuleViolation("content hash must be 64 hex characters")


def _check_data(data) -> None:
    if data is None:
        raise RuleViolation("attach_data needs a data reference")
    if not (
        data.data_uri.startswith("https://") or data.data_uri.startswith("ipfs://")
    ):
        raise RuleViolation("data_uri must start with https:// or ipfs://")
    _check_hash(data.content_hash)
    if not data.data_type or not data.step:
        raise RuleViolation("data type and step are required")
