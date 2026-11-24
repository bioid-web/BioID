"""Export a tube lineage from the bridge ledger as a GS1 EPCIS 2.0 document.

EPCIS 2.0 (ISO/IEC 19987:2024) is the common event format for "what, when,
where, why" in supply chains. This exporter lets a partner that already speaks
EPCIS read BioID custody history without learning the contract. It is a
prototype: identifiers are plain HTTPS URIs under a base the operator chooses,
not GS1 keys, and BioID-specific fields use the `bioid:` extension namespace.

Mapping (BioID op -> EPCIS):
  mint_primary          ObjectEvent ADD, bizStep commissioning, disposition active
  move                  ObjectEvent OBSERVE, bizStep storing, readPoint/bizLocation = wallet
  ship / receive        ObjectEvent OBSERVE, bizStep shipping / receiving
  transform             TransformationEvent, parent in, children out, bioid:reason
  burn                  ObjectEvent OBSERVE, bizStep other, bioid:reason (consumed, ...)
  adjust                ObjectEvent OBSERVE, bizStep inspecting
  withdraw              one ObjectEvent OBSERVE for the lineage, bizStep holding,
                        disposition unavailable
  confirm_destroyed     ObjectEvent DELETE, bizStep destroying, disposition destroyed
Access requests, approvals and data attachments are not physical events and
are left out. Volumes are carried as bioid:volumeUl / bioid:balanceUl because
EPCIS quantities describe classes, not single instances.
"""

from __future__ import annotations

from datetime import datetime, timezone

from bioid_bridge.ledger import MockLedger

EPCIS_CONTEXT = "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld"
BIOID_NS = "https://bioid-web.github.io/BioID/ns/epcis#"
DEFAULT_BASE = "https://example.org/bioid/"

_LINEAGE_WIDE = frozenset({"withdraw", "unfreeze_anonymised"})

_OBJECT = {
    "move": ("OBSERVE", "storing", "active"),
    "ship": ("OBSERVE", "shipping", "in_transit"),
    "receive": ("OBSERVE", "receiving", "active"),
    "burn": ("OBSERVE", "other", None),
    "adjust": ("OBSERVE", "inspecting", None),
    "withdraw": ("OBSERVE", "holding", "unavailable"),
    "unfreeze_anonymised": ("OBSERVE", "other", "active"),
    "confirm_destroyed": ("DELETE", "destroying", "destroyed"),
}


def _iso(value: str | None) -> str:
    if value:
        return value
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _offset(iso: str) -> str:
    try:
        moment = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "+00:00"
    offset = moment.utcoffset()
    if offset is None:
        return "+00:00"
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    minutes = abs(minutes)
    return f"{sign}{minutes // 60:02d}:{minutes % 60:02d}"


class EpcisExporter:
    def __init__(self, ledger: MockLedger, base: str = DEFAULT_BASE):
        if not base.startswith("https://"):
            raise ValueError("base must be an https:// URI")
        self.ledger = ledger
        self.base = base if base.endswith("/") else base + "/"

    def tube_uri(self, tube: str) -> str:
        return f"{self.base}tube/{tube}"

    def wallet_uri(self, label: str) -> str:
        return f"{self.base}wallet/{label}"

    def lineage_tubes(self, tube: str) -> list[str]:
        token = self.ledger.token(tube)
        if token is None:
            raise KeyError(tube)
        rows = self.ledger.conn.execute(
            "SELECT tube FROM tokens WHERE root_id = ? ORDER BY tube", (token["root_id"],)
        ).fetchall()
        return [row["tube"] for row in rows]

    def document(self, tube: str, *, created: str | None = None) -> dict:
        """EPCIS 2.0 document for the whole lineage that contains `tube`."""
        tubes = self.lineage_tubes(tube)
        placeholders = ",".join("?" for _ in tubes)
        rows = self.ledger.conn.execute(
            f"SELECT * FROM history WHERE tube IN ({placeholders}) ORDER BY id", tubes
        ).fetchall()
        events: list[dict] = []
        transformed: set[tuple[str, str]] = set()
        grouped: dict[tuple[str, str], dict] = {}
        for row in rows:
            row = dict(row)
            key = (row["event_id"], row["op"])
            if row["op"] in _LINEAGE_WIDE and key in grouped:
                # One withdrawal touches every tube of the lineage: one event, many EPCs.
                grouped[key]["epcList"].append(self.tube_uri(row["tube"]))
                continue
            event = self._event(row, transformed)
            if event is not None:
                if row["op"] in _LINEAGE_WIDE:
                    for field in ("readPoint", "bizLocation", "bioid:volumeUl", "bioid:balanceUl"):
                        event.pop(field, None)
                    grouped[key] = event
                events.append(event)
        return {
            "@context": [EPCIS_CONTEXT, {"bioid": BIOID_NS}],
            "type": "EPCISDocument",
            "schemaVersion": "2.0",
            "creationDate": _iso(created),
            "epcisBody": {"eventList": events},
        }

    def _base_event(self, row: dict, kind: str) -> dict:
        when = _iso(row.get("occurred_at") or row.get("recorded_at"))
        event = {
            "type": kind,
            "eventTime": when,
            "eventTimeZoneOffset": _offset(when),
            "eventID": f"{self.base}event/{row['event_id']}/{row['id']}",
            "bioid:op": row["op"],
            "bioid:reason": row["reason"],
            "bioid:limsEventId": row["event_id"],
        }
        if row.get("recorded_at"):
            event["recordTime"] = row["recorded_at"]
        return event

    def _event(self, row: dict, transformed: set[tuple[str, str]]) -> dict | None:
        op = row["op"]
        if op == "transform":
            key = (row["event_id"], row["tube"])
            if key in transformed:
                return None
            transformed.add(key)
            event = self._base_event(row, "TransformationEvent")
            children = [c for c in (row.get("related_tube") or "").split(",") if c]
            event["inputEPCList"] = [self.tube_uri(row["tube"])]
            event["outputEPCList"] = [self.tube_uri(child) for child in children]
            event["bioid:burnUl"] = row["volume_ul"]
            if row.get("added_ul") is not None:
                event["bioid:addedUl"] = row["added_ul"]
            if row.get("from_wallet"):
                event["bizLocation"] = {"id": self.wallet_uri(row["from_wallet"])}
            return event
        if op == "mint":
            return None  # child mints are covered by their TransformationEvent
        if op == "mint_primary":
            event = self._base_event(row, "ObjectEvent")
            event.update(action="ADD", bizStep="commissioning", disposition="active")
        elif op in _OBJECT:
            action, step, disposition = _OBJECT[op]
            event = self._base_event(row, "ObjectEvent")
            event.update(action=action, bizStep=step)
            if disposition:
                event["disposition"] = disposition
        else:
            return None
        event["epcList"] = [self.tube_uri(row["tube"])]
        wallet = row.get("to_wallet") or row.get("from_wallet")
        if wallet:
            event["readPoint"] = {"id": self.wallet_uri(wallet)}
            event["bizLocation"] = {"id": self.wallet_uri(wallet)}
        if op == "ship" and row.get("from_wallet") and row.get("to_wallet"):
            event["sourceList"] = [
                {"type": "location", "source": self.wallet_uri(row["from_wallet"])}
            ]
            event["destinationList"] = [
                {"type": "location", "destination": self.wallet_uri(row["to_wallet"])}
            ]
        if row.get("volume_ul") is not None:
            event["bioid:volumeUl"] = row["volume_ul"]
        if row.get("balance_after") is not None:
            event["bioid:balanceUl"] = row["balance_after"]
        return event
