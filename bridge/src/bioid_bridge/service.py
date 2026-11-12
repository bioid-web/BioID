"""Replay LIMS events: translate, validate, batch, retry, and queue exceptions."""

from __future__ import annotations

from bioid_bridge.ledger import MockLedger
from bioid_bridge.mapping import Mapping, translate
from bioid_bridge.model import MappingError, ReplayReport, RuleViolation, TransientChainError
from bioid_bridge.registry import Registry


def _chunks(items: list[dict], size: int) -> list[list[dict]]:
    if size < 1:
        raise ValueError("batch size must be at least 1")
    return [items[index : index + size] for index in range(0, len(items), size)]


class LimsBridge:
    def __init__(
        self,
        *,
        registry: Registry,
        mapping: Mapping,
        ledger: MockLedger,
        batch_size: int = 8,
        max_retries: int = 3,
        backend=None,
    ):
        self.registry = registry
        self.mapping = mapping
        self.ledger = ledger
        self.backend = ledger if backend is None else backend
        self.batch_size = batch_size
        self.max_retries = max_retries

    def replay(self, events: list[dict]) -> ReplayReport:
        skipped = [event["event_id"] for event in events if self.ledger.is_applied(event["event_id"])]
        pending = [event for event in events if not self.ledger.is_applied(event["event_id"])]
        batches: list[str] = []
        for chunk in _chunks(pending, self.batch_size):
            batches.extend(self._commit_chunk(chunk))
        applied = [event["event_id"] for event in pending if self.ledger.is_applied(event["event_id"])]
        queued = [event["event_id"] for event in pending if not self.ledger.is_applied(event["event_id"])]
        return ReplayReport(applied=applied, skipped=skipped, queued=queued, batches=batches)

    def _commit_chunk(self, events: list[dict]) -> list[str]:
        try:
            ops = [translate(event, self.mapping) for event in events]
        except MappingError:
            return self._one_by_one(events)
        error: TransientChainError | None = None
        for _attempt in range(self.max_retries):
            try:
                batch_id = self.backend.submit(ops)
            except TransientChainError as exc:
                error = exc
                continue
            except RuleViolation:
                return self._one_by_one(events)
            for event in events:
                self.ledger.clear_review(event["event_id"])
            return [batch_id]
        assert error is not None
        for event in events:
            if not self.ledger.is_applied(event["event_id"]):
                self.ledger.enqueue_review(event["event_id"], f"transient failure: {error}", event)
        return []

    def _one_by_one(self, events: list[dict]) -> list[str]:
        batches: list[str] = []
        for event in events:
            if self.ledger.is_applied(event["event_id"]):
                continue
            try:
                op = translate(event, self.mapping)
            except MappingError as exc:
                self.ledger.enqueue_review(event["event_id"], str(exc), event)
                continue
            error: TransientChainError | None = None
            for _attempt in range(self.max_retries):
                try:
                    batch_id = self.backend.submit([op])
                except TransientChainError as exc:
                    error = exc
                    continue
                except RuleViolation as exc:
                    self.ledger.enqueue_review(event["event_id"], str(exc), event)
                    error = None
                    break
                self.ledger.clear_review(event["event_id"])
                batches.append(batch_id)
                error = None
                break
            if error is not None:
                self.ledger.enqueue_review(
                    event["event_id"], f"transient failure: {error}", event
                )
        return batches
