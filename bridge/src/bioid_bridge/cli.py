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

    fp = sub.add_parser(
        "fingerprint",
        help="SHA-256 fingerprint of a document for attach_data; --salt-file for guessable documents",
    )
    fp.add_argument("--file", required=True, type=Path)
    fp.add_argument("--salt-file", type=Path, help="read the salt from this file (raw bytes)")
    fp.add_argument("--new-salt", type=Path, help="write a fresh random salt to this file and use it")
    fp.add_argument("--verify", help="expected 64-hex fingerprint; exit 1 if it does not match")

    ep = sub.add_parser("export-epcis", help="write a tube lineage as a GS1 EPCIS 2.0 JSON-LD document")
    ep.add_argument("--tube", required=True)
    ep.add_argument("--db", required=True, type=Path)
    ep.add_argument("--base", default="https://example.org/bioid/", help="https base for tube and wallet URIs")
    ep.add_argument("--out", type=Path, help="write to this file instead of stdout")
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


def _cmd_fingerprint(args: argparse.Namespace) -> int:
    from bioid_bridge.fingerprint import fingerprint, new_salt, verify

    content = args.file.read_bytes()
    salt = None
    if args.salt_file and args.new_salt:
        print("use --salt-file or --new-salt, not both")
        return 2
    if args.new_salt:
        if args.new_salt.exists():
            print(f"{args.new_salt} exists; refusing to overwrite a salt")
            return 2
        salt = new_salt()
        args.new_salt.write_bytes(salt)
    elif args.salt_file:
        salt = args.salt_file.read_bytes()
    if args.verify:
        ok = verify(content, args.verify, salt)
        print("match" if ok else "MISMATCH")
        return 0 if ok else 1
    print(fingerprint(content, salt))
    return 0


def _cmd_export_epcis(args: argparse.Namespace) -> int:
    from bioid_bridge.epcis import EpcisExporter

    ledger = MockLedger(args.db)
    try:
        try:
            document = EpcisExporter(ledger, args.base).document(args.tube)
        except KeyError:
            print(f"unknown tube {args.tube}")
            return 2
    finally:
        ledger.close()
    text = json.dumps(document, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


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
    if args.command == "fingerprint":
        return _cmd_fingerprint(args)
    if args.command == "export-epcis":
        return _cmd_export_epcis(args)
    parser.error(f"unknown command {args.command}")
    return 2
