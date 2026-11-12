"""Command line for the reference bridge."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bioid_bridge.ledger import MockLedger
from bioid_bridge.mapping import load_events, load_mapping
from bioid_bridge.reconcile import reconcile
from bioid_bridge.registry import load_registry
from bioid_bridge.service import LimsBridge


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bioid-bridge",
        description="Reference LIMS bridge. Synthetic data only. Signs nothing on a public chain.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    replay = sub.add_parser("replay", help="translate a LIMS event feed and apply it to the ledger")
    replay.add_argument("--events", required=True, type=Path)
    replay.add_argument("--mapping", required=True, type=Path)
    replay.add_argument("--registry", required=True, type=Path)
    replay.add_argument("--db", required=True, type=Path)
    replay.add_argument("--batch-size", type=int, default=8)
    replay.add_argument("--retries", type=int, default=3)

    history = sub.add_parser("history", help="show one tube's transfers and parent chain")
    history.add_argument("--tube", required=True)
    history.add_argument("--db", required=True, type=Path)

    inventory = sub.add_parser("inventory", help="list tubes held by a wallet")
    inventory.add_argument("--wallet", required=True, help="registry label, for example SYN-FRZ-LT80")
    inventory.add_argument("--db", required=True, type=Path)
    inventory.add_argument("--all", action="store_true", help="include zero-balance tokens")

    rec = sub.add_parser("reconcile", help="compare a LIMS inventory snapshot with the ledger")
    rec.add_argument("--inventory", required=True, type=Path)
    rec.add_argument("--mapping", required=True, type=Path)
    rec.add_argument("--db", required=True, type=Path)
    return parser


def _cmd_replay(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry)
    mapping = load_mapping(args.mapping)
    ledger = MockLedger(args.db, registry)
    try:
        bridge = LimsBridge(
            registry=registry,
            mapping=mapping,
            ledger=ledger,
            batch_size=args.batch_size,
            max_retries=args.retries,
        )
        report = bridge.replay(load_events(args.events))
    finally:
        ledger.close()
    print(report.format())
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    ledger = MockLedger(args.db)
    try:
        try:
            lineage = ledger.lineage(args.tube)
        except KeyError:
            print(f"unknown tube {args.tube}")
            return 2
        print(f"tube {lineage['tube']}")
        print(f"root {lineage['root_id']}")
        print("lineage " + " -> ".join(lineage["root_to_tube"]))
        children = ", ".join(lineage["children"]) if lineage["children"] else "(none)"
        print(f"children {children}")
        print("history")
        for row in ledger.history(args.tube):
            route = ""
            if row["from_wallet"] or row["to_wallet"]:
                route = f" {row['from_wallet'] or '-'} -> {row['to_wallet'] or '-'}"
            related = f" related {row['related_tube']}" if row["related_tube"] else ""
            print(
                f"  {row['event_id']} {row['op']} {row['reason']}{route} "
                f"volume {row['volume_ul']} balance {row['balance_after']}{related}"
            )
    finally:
        ledger.close()
    return 0


def _cmd_inventory(args: argparse.Namespace) -> int:
    ledger = MockLedger(args.db)
    try:
        rows = ledger.inventory(args.wallet, positive_only=not args.all)
    finally:
        ledger.close()
    print(f"{args.wallet} ({len(rows)})")
    for row in rows:
        print(f"  {row['tube']} {row['balance_ul']} µL {row['sample_type'] or ''}".rstrip())
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    mapping = load_mapping(args.mapping)
    document = json.loads(args.inventory.read_text(encoding="utf-8"))
    ledger = MockLedger(args.db)
    try:
        report = reconcile(ledger, mapping, document)
    finally:
        ledger.close()
    print(report.format())
    return 1 if report.mismatches else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "replay":
        return _cmd_replay(args)
    if args.command == "history":
        return _cmd_history(args)
    if args.command == "inventory":
        return _cmd_inventory(args)
    if args.command == "reconcile":
        return _cmd_reconcile(args)
    parser.error(f"unknown command {args.command}")
    return 2
