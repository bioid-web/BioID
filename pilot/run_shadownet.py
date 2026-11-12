#!/usr/bin/env python3
"""Replay the synthetic pilot feed on the Tezos Shadownet testnet.

Shadownet only. This script refuses mainnet, refuses any RPC that is not a
Shadownet endpoint, checks the chain id before every run, and does nothing
live unless BIOID_LIVE_SHADOWNET=1 is set. Without that flag it prints the
octez-client calls it would make (dry run).

Keys never live in this repository. Signing is delegated to octez-client
with an operator-owned base directory (TEZOS_CLIENT_DIR) that must sit
outside the repository. The script looks up the alias for each custodian
address in that directory; it never reads or prints a secret key.

Usage (from the repository root):

    export TEZOS_NETWORK=shadownet
    export TEZOS_RPC_URL=https://rpc.shadownet.teztnets.com
    export TEZOS_CLIENT_DIR=/path/outside/repo/octez-shadownet
    python3 pilot/run_shadownet.py register      # dry run
    BIOID_LIVE_SHADOWNET=1 python3 pilot/run_shadownet.py register
    BIOID_LIVE_SHADOWNET=1 python3 pilot/run_shadownet.py replay

Every injected operation hash is appended to
pilot/deployments/shadownet.json under "operations".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "pilot"
SHADOWNET_CHAIN_ID = "NetXsqzbfFenSTS"
MAINNET_MARKERS = ("mainnet", "rpc.tzbeta.net", "mainnet.api.tez.ie")
OCTEZ = os.environ.get("OCTEZ_CLIENT", "octez-client")


class Refused(SystemExit):
    pass


# --------------------------------------------------------------------------- guards


def guard() -> tuple[str, bool]:
    network = os.environ.get("TEZOS_NETWORK", "").strip().lower()
    rpc = os.environ.get("TEZOS_RPC_URL", "").strip()
    if network == "mainnet" or any(m in rpc.lower() for m in MAINNET_MARKERS):
        raise Refused("refused: mainnet is never a target for this script")
    if network != "shadownet":
        raise Refused("refused: TEZOS_NETWORK must be shadownet")
    if "shadownet" not in rpc.lower():
        raise Refused("refused: TEZOS_RPC_URL must be a Shadownet endpoint")
    client_dir = os.environ.get("TEZOS_CLIENT_DIR", "").strip()
    if not client_dir:
        raise Refused("refused: TEZOS_CLIENT_DIR (octez-client base dir outside the repo) is required")
    if Path(client_dir).resolve().is_relative_to(ROOT):
        raise Refused("refused: TEZOS_CLIENT_DIR must not be inside the repository")
    with urllib.request.urlopen(rpc.rstrip("/") + "/chains/main/chain_id", timeout=20) as r:
        chain_id = json.loads(r.read())
    if chain_id != SHADOWNET_CHAIN_ID:
        raise Refused(f"refused: chain id {chain_id} is not Shadownet ({SHADOWNET_CHAIN_ID})")
    live = os.environ.get("BIOID_LIVE_SHADOWNET", "") == "1"
    return rpc, live


# --------------------------------------------------------------------------- michelson


def mstr(s: str) -> str:
    if not all(32 <= ord(c) < 127 for c in s) or '"' in s or "\\" in s:
        raise ValueError(f"string not safe for Michelson literal: {s!r}")
    return f'"{s}"'


def mbytes_utf8(s: str) -> str:
    return "0x" + s.encode().hex()


def sha256_bytes(s: str) -> str:
    return "0x" + hashlib.sha256(s.encode()).hexdigest()


def mopt(v: str | None) -> str:
    return "None" if v is None else f"(Some {v})"


def pair(*xs: str) -> str:
    out = xs[-1]
    for x in reversed(xs[:-1]):
        out = f"(Pair {x} {out})"
    return out


def mdata(d: dict | None) -> str:
    if d is None:
        return "None"
    digest = d["content_sha256"].lower().removeprefix("0x")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("content_sha256 must be 64 hex digits")
    inner = pair(
        mopt(mstr(d["access_level"]) if d.get("access_level") else None),
        "0x" + digest,
        mstr(d["data_type"]),
        mstr(d["data_uri"]),
        mopt(mstr(d["licence"]) if d.get("licence") else None),
        mstr(d["step"]),
    )
    return f"(Some {inner})"


def mdata_required(d: dict) -> str:
    return mdata(d)[len("(Some ") : -1]


# --------------------------------------------------------------------------- deployment


class Deployment:
    def __init__(self, path: Path):
        self.path = path
        self.doc = json.loads(path.read_text())
        if self.doc.get("network") != "shadownet" or self.doc.get("chain_id") != SHADOWNET_CHAIN_ID:
            raise Refused("refused: deployment file is not a Shadownet deployment")
        self.contract = self.doc["contract"]["address"]
        self.by_label = {w["label"]: w for w in self.doc["wallets"]}
        mapping = json.loads((PILOT / "lims-mapping.json").read_text())
        self.location = mapping["locations"]

    def wallet(self, location: str) -> dict:
        return self.by_label[self.location[location]]

    def record(self, entry: dict) -> None:
        self.doc.setdefault("operations", []).append(entry)
        self.path.write_text(json.dumps(self.doc, indent=2, ensure_ascii=False) + "\n")


# --------------------------------------------------------------------------- octez-client


def aliases() -> dict[str, str]:
    out = subprocess.run([OCTEZ, "list", "known", "addresses"], capture_output=True, text=True, check=True).stdout
    result = {}
    for line in out.splitlines():
        m = re.match(r"^\s*([\w.-]+): (tz[1-4]\w{33})", line)
        if m:
            result[m.group(2)] = m.group(1)
    return result


class Chain:
    def __init__(self, rpc: str, live: bool, dep: Deployment):
        self.rpc, self.live, self.dep = rpc, live, dep
        self.alias = aliases() if live else {}

    def call(self, signer: str, entrypoint: str, arg: str, label: str, event_id: str | None = None) -> str | None:
        alias = self.alias.get(signer, signer) if self.live else signer
        cmd = [OCTEZ, "--endpoint", self.rpc, "transfer", "0", "from", alias, "to", self.dep.contract,
               "--entrypoint", entrypoint, "--arg", arg, "--burn-cap", "1"]
        if not self.live:
            print(f"[dry-run] {label}: {entrypoint} signed by {signer}\n  {arg}")
            return None
        if signer not in self.alias:
            raise Refused(f"no octez-client alias for signer {signer} in TEZOS_CLIENT_DIR")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        text = proc.stdout + proc.stderr
        m = re.search(r"Operation hash is '(o\w{50})'", text)
        if proc.returncode != 0 or not m:
            tail = "\n".join(l for l in text.splitlines() if "rror" in l or "BIOID" in l or "FA2" in l)
            raise SystemExit(f"{label}: {entrypoint} failed\n{tail or text[-2000:]}")
        op = m.group(1)
        self.dep.record({
            "event_id": event_id, "step": label, "entrypoint": entrypoint, "signer": signer,
            "operation": op, "tzkt": f"https://shadownet.tzkt.io/{op}",
        })
        print(f"{label}: {entrypoint} -> https://shadownet.tzkt.io/{op}")
        return op

    def next_request_id(self) -> int:
        url = f"{self.rpc.rstrip('/')}/chains/main/blocks/head/context/contracts/{self.dep.contract}/storage"
        with urllib.request.urlopen(url, timeout=20) as r:
            storage = json.loads(r.read())
        # storage is a right-comb; field 9 (0-based) is next_request_id
        def flat(node):
            if isinstance(node, list):
                return [x for item in node for x in flat(item)]
            if isinstance(node, dict) and node.get("prim") == "Pair":
                return [x for item in node["args"] for x in flat(item)]
            return [node]

        return int(flat(storage)[9]["int"])


# --------------------------------------------------------------------------- steps


def register(chain: Chain) -> None:
    dep = chain.dep
    admin = dep.doc["admin"]["address"]
    for w in dep.doc["wallets"]:
        arg = pair(
            "True",
            mstr(w["address"]),
            mstr(w["custodian"]["address"]),
            mstr(w["label"]),
            mstr(w["metadata_uri"]),
            mopt(mstr(w["parent_location"]) if w["parent_location"] else None),
            mstr(w.get("process", "")),
            mstr(w["site"]),
            mstr(w["type"]),
        )
        chain.call(admin, "register_wallet", arg, f"register {w['label']}")


def replay(chain: Chain, events_path: Path, start: str | None) -> None:
    dep = chain.dep
    events = [json.loads(l) for l in events_path.read_text().splitlines() if l.strip()]
    holder: dict[str, str] = {}  # tube -> location code
    requests: dict[str, int] = {}
    started = start is None
    for ev in events:
        eid, kind, tube = ev["event_id"], ev["type"], ev["tube"]
        # keep the holder map current even for skipped events
        live_now = started or eid == start
        started = live_now
        label = f"{eid} {kind} {tube}"
        cur = holder.get(tube)

        def custodian(loc: str) -> str:
            return dep.wallet(loc)["custodian"]["address"]

        if kind == "collected":
            dest = dep.wallet(ev["to_location"])
            arg = pair(
                mstr(tube), mbytes_utf8(tube), mstr(ev["consent_ref"]), sha256_bytes(tube),
                mstr(f"https://example.org/synthetic/pilot/tubes/{tube}"),
                mstr(dep.doc["owners"][ev["owner"]]), mstr(ev["sample_type"]),
                mbytes_utf8(ev["sample_type"]), mstr(dest["address"]), str(ev["volume_uL"]),
            )
            if live_now:
                chain.call(custodian(ev["to_location"]), "mint_primary", arg, label, eid)
            holder[tube] = ev["to_location"]
        elif kind in ("to_process", "stored", "moved", "retrieval"):
            src = ev.get("from_location", cur)
            dest = dep.wallet(ev["to_location"])
            arg = pair(mstr(tube), mdata(ev.get("data")), mstr(kind), mstr(dest["address"]))
            if live_now:
                chain.call(custodian(src), "move", arg, label, eid)
            holder[tube] = ev["to_location"]
        elif kind in ("aliquoted", "rna_isolation"):
            src = ev.get("from_location", cur)
            children = []
            for c in ev["children"]:
                children.append(pair(
                    mstr(c["tube"]), mbytes_utf8(c["tube"]), mstr(c["sample_type"]),
                    mbytes_utf8(c["sample_type"]), mstr(dep.wallet(c["to_location"])["address"]),
                    str(c["volume_uL"]),
                ))
                holder[c["tube"]] = c["to_location"]
            arg = pair(
                str(ev["burn_uL"]), "{" + "; ".join(c[1:-1] for c in children) + "}", mstr(tube),
                mdata(ev.get("data")), mstr(kind), mbytes_utf8(kind),
            )
            if live_now:
                chain.call(custodian(src), "transform", arg, label, eid)
        elif kind == "data_attached":
            arg = pair(mstr(tube), mdata_required(ev["data"]))
            if live_now:
                chain.call(custodian(cur), "attach_data", arg, label, eid)
        elif kind == "access_requested":
            requester = dep.wallet("EXT-USER")["custodian"]["address"]
            arg = pair("0x" + ev["agreement_hash"], mstr(ev["agreement_ref"]), mstr(tube), mstr(ev["duo_codes"]))
            if live_now:
                requests[eid] = chain.next_request_id() if chain.live else 0
                chain.call(requester, "request_access", arg, label, eid)
            else:
                requests[eid] = chain.next_request_id() - 1 if chain.live else 0
        elif kind == "access_approved":
            rid = requests[ev["request_event_id"]]
            if live_now:
                chain.call(custodian(cur), "approve_access", str(rid), label, eid)
        elif kind == "shipped":
            src = ev.get("from_location", cur)
            dest = dep.wallet(ev["to_location"])
            arg = pair(mstr(tube), mdata(ev.get("data")), mstr(dest["address"]))
            if live_now:
                chain.call(custodian(src), "ship", arg, label, eid)
            holder[tube] = ev["to_location"]
        elif kind == "received":
            dest = dep.wallet(ev["to_location"])
            arg = pair(mstr(tube), mdata(ev.get("data")), mstr(dest["address"]))
            if live_now:
                chain.call(custodian(ev["to_location"]), "receive", arg, label, eid)
            holder[tube] = ev["to_location"]
        elif kind == "consumed":
            src = ev.get("from_location", cur)
            if dep.wallet(src)["type"] == "EXTERNAL_USER":
                arg = pair(mstr("consumed"), mstr(tube), mdata(ev.get("data")), "None", str(ev["burn_uL"]))
                ep = "report_use"
            else:
                arg = pair(str(ev["burn_uL"]), mstr(tube), mdata(ev.get("data")))
                ep = "consume"
            if live_now:
                chain.call(custodian(src), ep, arg, label, eid)
        else:
            raise SystemExit(f"{eid}: no on-chain mapping for event type {kind}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["register", "replay"])
    ap.add_argument("--deployment", default=str(PILOT / "deployments" / "shadownet.json"))
    ap.add_argument("--events", default=str(PILOT / "scenario.events.jsonl"))
    ap.add_argument("--from-event", default=None, help="resume the replay at this event_id")
    args = ap.parse_args()
    rpc, live = guard()
    dep = Deployment(Path(args.deployment))
    chain = Chain(rpc, live, dep)
    if not live:
        print("dry run: set BIOID_LIVE_SHADOWNET=1 to inject on Shadownet")
    if args.step == "register":
        register(chain)
    else:
        replay(chain, Path(args.events), args.from_event)


if __name__ == "__main__":
    main()
