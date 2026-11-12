"""Build initial storage for TEZOS_ADMIN. Does not originate.

Importing the contract module also runs its scenarios. That stays on this
machine. The admin address is read from the environment and is not written
into the repository.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import smartpy as sp

CONTRACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTRACTS))
os.chdir(CONTRACTS)

import bioid_fa2  # noqa: E402

admin = os.environ.get("TEZOS_ADMIN", "").strip()
if not admin:
    raise SystemExit("TEZOS_ADMIN is required")

scenario = sp.test_scenario("bioid_storage")
metadata = sp.scenario_utils.metadata_of_url(
    "https://example.org/synthetic/bioid/contract.json"
)
scenario += bioid_fa2.bioid.Bioid(sp.address(admin), metadata)
print(f"storage scenario written under {CONTRACTS / 'bioid_storage'}")
