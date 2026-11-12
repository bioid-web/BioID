import json
import os
import subprocess
import sys

from conftest import ROOT

SRC = ROOT / "bridge" / "src"


def test_cli_replay_history_inventory_and_reconcile(tmp_path):
    db = tmp_path / "bridge.sqlite"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    common = [sys.executable, "-m", "bioid_bridge"]
    replay = subprocess.run(
        common
        + [
            "replay",
            "--events",
            str(ROOT / "examples" / "lims-events.example.jsonl"),
            "--mapping",
            str(ROOT / "examples" / "lims-mapping.example.json"),
            "--registry",
            str(ROOT / "examples" / "wallet-registry.example.json"),
            "--db",
            str(db),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "applied: 15" in replay.stdout
    assert "queued: 0" in replay.stdout

    history = subprocess.run(
        common + ["history", "--tube", "SY00000107", "--db", str(db)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "SY00000101 -> SY00000103 -> SY00000105 -> SY00000107" in history.stdout
    assert "consumed" in history.stdout

    inventory = subprocess.run(
        common + ["inventory", "--wallet", "SYN-FRZ-LT80", "--db", str(db)],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "SY00000102 1000" in inventory.stdout
    assert "SY00000107 150" in inventory.stdout
    assert "SY00000106" not in inventory.stdout

    document = json.loads(
        (ROOT / "examples" / "lims-inventory.example.json").read_text(encoding="utf-8")
    )
    assert document["rows"][1]["tube"] == "SY00000106"
    rec = subprocess.run(
        common
        + [
            "reconcile",
            "--inventory",
            str(ROOT / "examples" / "lims-inventory.example.json"),
            "--mapping",
            str(ROOT / "examples" / "lims-mapping.example.json"),
            "--db",
            str(db),
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    assert rec.returncode == 1
    assert "mismatches: 1" in rec.stdout
    assert "SY00000106" in rec.stdout
