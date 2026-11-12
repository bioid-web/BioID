"""In-process FA2-like ledger. Balances are microlitres. Tokens remain at zero."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from bioid_bridge.model import Operation, RuleViolation, TransientChainError
from bioid_bridge.registry import Registry
from bioid_bridge.rules import validate


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class MockLedger:
    """SQLite ledger used when no chain is available.

    An applied LIMS event id is stored in the same transaction as the balance
    change. Replaying that id is a no-op, including a retry that lost the
    caller's acknowledgement after the commit.
    """

    def __init__(self, path: str | Path = ":memory:", registry: Registry | None = None):
        self.registry = registry
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.isolation_level = None
        self._transient_remaining = 0
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def fail_next(self, count: int) -> None:
        """The next `count` apply_batch calls raise TransientChainError before writing."""
        self._transient_remaining = count

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tokens (
              tube TEXT PRIMARY KEY,
              balance_ul INTEGER NOT NULL,
              wallet TEXT NOT NULL,
              parent_id TEXT,
              root_id TEXT NOT NULL,
              sample_type TEXT,
              created_by TEXT,
              owner TEXT,
              consent_ref TEXT,
              status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL,
              batch_id TEXT NOT NULL,
              tube TEXT NOT NULL,
              op TEXT NOT NULL,
              reason TEXT NOT NULL,
              from_wallet TEXT,
              to_wallet TEXT,
              volume_ul INTEGER,
              balance_after INTEGER,
              related_tube TEXT
            );
            CREATE TABLE IF NOT EXISTS applied_events (
              event_id TEXT PRIMARY KEY,
              batch_id TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS writeback (
              event_id TEXT PRIMARY KEY,
              lims_field TEXT NOT NULL,
              tx_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_queue (
              event_id TEXT PRIMARY KEY,
              message TEXT NOT NULL,
              payload TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attachments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL,
              tube TEXT NOT NULL,
              data_uri TEXT NOT NULL,
              content_hash TEXT NOT NULL,
              data_type TEXT NOT NULL,
              step TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS access_requests (
              event_id TEXT PRIMARY KEY,
              tube TEXT NOT NULL,
              agreement_ref TEXT NOT NULL,
              agreement_hash TEXT NOT NULL,
              duo_codes TEXT NOT NULL,
              status TEXT NOT NULL
            );
            """
        )

    def is_applied(self, event_id: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM applied_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row is not None

    def token(self, tube: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM tokens WHERE tube = ?", (tube,)).fetchone()
        return dict(row) if row else None

    def history(self, tube: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM history WHERE tube = ? ORDER BY id", (tube,)
        ).fetchall()
        return [dict(row) for row in rows]

    def lineage(self, tube: str) -> dict:
        token = self.token(tube)
        if token is None:
            raise KeyError(tube)
        chain = [tube]
        seen = {tube}
        cursor = token
        while cursor.get("parent_id") and cursor["parent_id"] not in seen:
            parent = self.token(cursor["parent_id"])
            if parent is None:
                break
            chain.append(parent["tube"])
            seen.add(parent["tube"])
            cursor = parent
        chain.reverse()
        children = [
            row["tube"]
            for row in self.conn.execute(
                "SELECT tube FROM tokens WHERE parent_id = ? ORDER BY tube", (tube,)
            )
        ]
        return {
            "tube": tube,
            "parent_id": token["parent_id"],
            "root_id": token["root_id"],
            "root_to_tube": chain,
            "children": children,
        }

    def inventory(self, wallet: str | None = None, *, positive_only: bool = True) -> list[dict]:
        clauses: list[str] = []
        params: list[object] = []
        if wallet is not None:
            clauses.append("wallet = ?")
            params.append(wallet)
        if positive_only:
            clauses.append("balance_ul > 0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM tokens {where} ORDER BY tube", params
        ).fetchall()
        return [dict(row) for row in rows]

    def review_queue(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM review_queue ORDER BY event_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def enqueue_review(self, event_id: str, message: str, payload: dict) -> None:
        self.conn.execute(
            """
            INSERT INTO review_queue(event_id, message, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
              message = excluded.message,
              payload = excluded.payload,
              updated_at = excluded.updated_at
            """,
            (event_id, message, json.dumps(payload, sort_keys=True), _now()),
        )

    def clear_review(self, event_id: str) -> None:
        self.conn.execute("DELETE FROM review_queue WHERE event_id = ?", (event_id,))

    def submit(self, ops: list[Operation]) -> str:
        """Chain-backend entry. The offline ledger applies the batch locally."""
        return self.apply_batch(ops)

    def apply_batch(self, ops: list[Operation]) -> str:
        if self._transient_remaining > 0:
            self._transient_remaining -= 1
            raise TransientChainError("injected transient failure")
        if self.registry is None:
            raise RuntimeError("a registry is required to apply operations")
        batch_id = "mock-" + hashlib.sha256(
            ",".join(op.event_id for op in ops).encode()
        ).hexdigest()
        self.conn.execute("BEGIN")
        try:
            for op in ops:
                self._apply(op, batch_id)
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        self.conn.execute("COMMIT")
        return batch_id

    def _apply(self, op: Operation, batch_id: str) -> None:
        if self.is_applied(op.event_id):
            return
        assert self.registry is not None
        token = self.token(op.tube)
        validate(op, token, self.registry)
        if op.op == "mint_primary":
            self._mint_primary(op, batch_id)
        elif op.op in {"move", "ship", "receive"}:
            self._transfer(op, batch_id, token)
        elif op.op == "transform":
            self._transform(op, batch_id, token)
        elif op.op == "burn":
            self._burn(op, batch_id, token)
        elif op.op == "adjust":
            self._adjust(op, batch_id, token)
        elif op.op == "attach_data":
            self._attach(op, batch_id, token)
        elif op.op == "access_request":
            self._access_request(op, batch_id)
        elif op.op == "access_approve":
            self._access_approve(op, batch_id, token)
        else:
            raise RuleViolation(f"unknown operation {op.op}")
        if op.data is not None and op.op != "attach_data":
            self._insert_attachment(op, op.tube)
        self.conn.execute(
            "INSERT INTO applied_events(event_id, batch_id) VALUES (?, ?)",
            (op.event_id, batch_id),
        )
        self.conn.execute(
            "INSERT INTO writeback(event_id, lims_field, tx_hash) VALUES (?, 'bioid_tx', ?)",
            (op.event_id, batch_id),
        )

    def _status_for(self, wallet_label: str) -> str:
        assert self.registry is not None
        kind = self.registry.get(wallet_label).type
        if kind == "TRANSIT":
            return "in_transit"
        if kind == "PROCESS":
            return "in_process"
        return "active"

    def _history(
        self,
        op: Operation,
        batch_id: str,
        *,
        tube: str,
        op_name: str,
        from_wallet: str | None,
        to_wallet: str | None,
        volume_ul: int | None,
        balance_after: int | None,
        related_tube: str | None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO history(
              event_id, batch_id, tube, op, reason, from_wallet, to_wallet,
              volume_ul, balance_after, related_tube
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                op.event_id,
                batch_id,
                tube,
                op_name,
                op.reason,
                from_wallet,
                to_wallet,
                volume_ul,
                balance_after,
                related_tube,
            ),
        )

    def _mint_primary(self, op: Operation, batch_id: str) -> None:
        assert op.volume_uL is not None and op.to_wallet is not None
        self.conn.execute(
            """
            INSERT INTO tokens(
              tube, balance_ul, wallet, parent_id, root_id, sample_type,
              created_by, owner, consent_ref, status
            ) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
            """,
            (
                op.tube,
                op.volume_uL,
                op.to_wallet,
                op.tube,
                op.sample_type,
                op.reason,
                op.owner,
                op.consent_ref,
                self._status_for(op.to_wallet),
            ),
        )
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="mint_primary",
            from_wallet=None,
            to_wallet=op.to_wallet,
            volume_ul=op.volume_uL,
            balance_after=op.volume_uL,
            related_tube=None,
        )

    def _transfer(self, op: Operation, batch_id: str, token: dict | None) -> None:
        assert token is not None and op.to_wallet is not None and self.registry is not None
        source = self.registry.get(token["wallet"])
        dest = self.registry.get(op.to_wallet)
        if op.op == "ship" and source.process == "retrieval":
            self._require_approval(op.tube)
        if op.op == "receive" and dest.type == "EXTERNAL_USER":
            self._require_approval(op.tube)
        self.conn.execute(
            "UPDATE tokens SET wallet = ?, status = ? WHERE tube = ?",
            (op.to_wallet, self._status_for(op.to_wallet), op.tube),
        )
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name=op.op,
            from_wallet=token["wallet"],
            to_wallet=op.to_wallet,
            volume_ul=token["balance_ul"],
            balance_after=token["balance_ul"],
            related_tube=None,
        )

    def _transform(self, op: Operation, batch_id: str, token: dict | None) -> None:
        assert token is not None and op.burn_uL is not None
        balance_after = token["balance_ul"] - op.burn_uL
        self.conn.execute(
            "UPDATE tokens SET balance_ul = ? WHERE tube = ?",
            (balance_after, op.tube),
        )
        child_ids = ",".join(child.tube for child in op.children)
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="transform",
            from_wallet=token["wallet"],
            to_wallet=token["wallet"],
            volume_ul=op.burn_uL,
            balance_after=balance_after,
            related_tube=child_ids,
        )
        for child in op.children:
            if self.token(child.tube) is not None:
                raise RuleViolation(f"{child.tube} already exists")
            self.conn.execute(
                """
                INSERT INTO tokens(
                  tube, balance_ul, wallet, parent_id, root_id, sample_type,
                  created_by, owner, consent_ref, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    child.tube,
                    child.volume_uL,
                    child.to_wallet,
                    op.tube,
                    token["root_id"],
                    child.sample_type,
                    op.reason,
                    token["owner"],
                    token["consent_ref"],
                    self._status_for(child.to_wallet),
                ),
            )
            self._history(
                op,
                batch_id,
                tube=child.tube,
                op_name="mint",
                from_wallet=None,
                to_wallet=child.to_wallet,
                volume_ul=child.volume_uL,
                balance_after=child.volume_uL,
                related_tube=op.tube,
            )

    def _burn(self, op: Operation, batch_id: str, token: dict | None) -> None:
        assert token is not None and op.burn_uL is not None
        balance_after = token["balance_ul"] - op.burn_uL
        self.conn.execute(
            "UPDATE tokens SET balance_ul = ? WHERE tube = ?",
            (balance_after, op.tube),
        )
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="burn",
            from_wallet=token["wallet"],
            to_wallet=token["wallet"],
            volume_ul=op.burn_uL,
            balance_after=balance_after,
            related_tube=None,
        )

    def attachments(self, tube: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM attachments WHERE tube = ? ORDER BY id", (tube,)
        ).fetchall()
        return [dict(row) for row in rows]

    def access_status(self, tube: str) -> str | None:
        row = self.conn.execute(
            """
            SELECT status FROM access_requests
            WHERE tube = ? ORDER BY event_id DESC LIMIT 1
            """,
            (tube,),
        ).fetchone()
        return None if row is None else row["status"]

    def _require_approval(self, tube: str) -> None:
        row = self.conn.execute(
            "SELECT 1 FROM access_requests WHERE tube = ? AND status = 'approved'",
            (tube,),
        ).fetchone()
        if row is None:
            raise RuleViolation(f"{tube} has no approved access request")

    def _insert_attachment(self, op: Operation, tube: str) -> None:
        assert op.data is not None
        self.conn.execute(
            """
            INSERT INTO attachments(
              event_id, tube, data_uri, content_hash, data_type, step
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                op.event_id,
                tube,
                op.data.data_uri,
                op.data.content_hash,
                op.data.data_type,
                op.data.step,
            ),
        )

    def _attach(self, op: Operation, batch_id: str, token: dict | None) -> None:
        assert token is not None
        self._insert_attachment(op, op.tube)
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="attach_data",
            from_wallet=token["wallet"],
            to_wallet=token["wallet"],
            volume_ul=None,
            balance_after=token["balance_ul"],
            related_tube=None,
        )

    def _access_request(self, op: Operation, batch_id: str) -> None:
        assert op.agreement_ref and op.agreement_hash and op.duo_codes
        self.conn.execute(
            """
            INSERT INTO access_requests(
              event_id, tube, agreement_ref, agreement_hash, duo_codes, status
            ) VALUES (?, ?, ?, ?, ?, 'pending')
            """,
            (op.event_id, op.tube, op.agreement_ref, op.agreement_hash, op.duo_codes),
        )
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="access_request",
            from_wallet=None,
            to_wallet=None,
            volume_ul=None,
            balance_after=None,
            related_tube=None,
        )

    def _access_approve(self, op: Operation, batch_id: str, token: dict | None) -> None:
        assert token is not None and op.request_event_id
        row = self.conn.execute(
            "SELECT tube, status FROM access_requests WHERE event_id = ?",
            (op.request_event_id,),
        ).fetchone()
        if row is None or row["tube"] != op.tube or row["status"] != "pending":
            raise RuleViolation(f"no pending access request {op.request_event_id}")
        self.conn.execute(
            "UPDATE access_requests SET status = 'approved' WHERE event_id = ?",
            (op.request_event_id,),
        )
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="access_approve",
            from_wallet=token["wallet"],
            to_wallet=token["wallet"],
            volume_ul=None,
            balance_after=token["balance_ul"],
            related_tube=op.request_event_id,
        )

    def _adjust(self, op: Operation, batch_id: str, token: dict | None) -> None:
        assert token is not None and op.volume_uL is not None
        self.conn.execute(
            "UPDATE tokens SET balance_ul = ? WHERE tube = ?",
            (op.volume_uL, op.tube),
        )
        self._history(
            op,
            batch_id,
            tube=op.tube,
            op_name="adjust",
            from_wallet=token["wallet"],
            to_wallet=token["wallet"],
            volume_ul=op.volume_uL,
            balance_after=op.volume_uL,
            related_tube=None,
        )
