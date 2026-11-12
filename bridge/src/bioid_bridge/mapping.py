"""Translate LIMS locations and event types into chain operations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bioid_bridge.model import Child, DataRef, MappingError, Operation

_PUBLIC_OPS = {
    "MOVE": "move",
    "SHIP": "ship",
    "RECEIVE": "receive",
    "BURN": "burn",
    "ADJUST": "adjust",
    "MINT": "mint",
    "DATA": "attach_data",
    "ACCESS_REQUEST": "access_request",
    "ACCESS_APPROVE": "access_approve",
}


@dataclass
class Mapping:
    locations: dict[str, str]
    events: dict[str, dict[str, str]]
    notice: str = ""

    def wallet_for(self, location: str) -> str:
        try:
            return self.locations[location]
        except KeyError as exc:
            raise MappingError(f"unknown LIMS location {location}") from exc

    def spec_for(self, event_type: str) -> dict[str, str]:
        try:
            return self.events[event_type]
        except KeyError as exc:
            raise MappingError(f"unknown LIMS event type {event_type}") from exc


def load_mapping(path: str | Path) -> Mapping:
    file_path = Path(path)
    suffix = file_path.suffix.lower()
    text = file_path.read_text(encoding="utf-8")
    if suffix == ".json":
        document = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise MappingError(
                "reading YAML needs PyYAML; use the JSON mapping or install PyYAML"
            ) from exc
        document = yaml.safe_load(text)
    else:
        raise MappingError(f"unsupported mapping file {file_path.name}")
    events = {key: dict(value) for key, value in document["events"].items()}
    return Mapping(
        locations=dict(document["locations"]),
        events=events,
        notice=str(document.get("notice", "")),
    )


def load_events(path: str | Path) -> list[dict]:
    events: list[dict] = []
    for line_number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MappingError(f"{path}:{line_number} is not JSON") from exc
        if not isinstance(event, dict):
            raise MappingError(f"{path}:{line_number} is not an object")
        events.append(event)
    return events


def _as_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MappingError(f"{field} must be an integer number of microlitres")
    return value


def translate(event: dict, mapping: Mapping) -> Operation:
    event_id = event.get("event_id")
    event_type = event.get("type")
    tube = event.get("tube")
    if not isinstance(event_id, str) or not event_id:
        raise MappingError("event_id is required")
    if not isinstance(event_type, str) or not event_type:
        raise MappingError(f"{event_id} has no type")
    if not isinstance(tube, str) or not tube:
        raise MappingError(f"{event_id} has no tube")

    spec = mapping.spec_for(event_type)
    public = spec.get("operation")
    reason = spec.get("reason")
    if public not in _PUBLIC_OPS or not isinstance(reason, str) or not reason:
        raise MappingError(f"{event_id} maps to an incomplete operation")

    children_raw = event.get("children") or []
    if not isinstance(children_raw, list):
        raise MappingError(f"{event_id} children must be a list")
    children: list[Child] = []
    for child in children_raw:
        if not isinstance(child, dict):
            raise MappingError(f"{event_id} has a child that is not an object")
        child_tube = child.get("tube")
        if not isinstance(child_tube, str) or not child_tube:
            raise MappingError(f"{event_id} has a child without a tube")
        location = child.get("to_location")
        if not isinstance(location, str):
            raise MappingError(f"{event_id} child {child_tube} has no to_location")
        sample_type = child.get("sample_type")
        children.append(
            Child(
                tube=child_tube,
                volume_uL=_as_int(child.get("volume_uL"), f"{child_tube} volume_uL"),
                sample_type=sample_type if isinstance(sample_type, str) else None,
                to_wallet=mapping.wallet_for(location),
            )
        )

    if public == "MINT" and children:
        op_name = "transform"
    elif public == "MINT":
        op_name = "mint_primary"
    else:
        op_name = _PUBLIC_OPS[public]

    to_wallet = None
    if event.get("to_location") is not None:
        to_wallet = mapping.wallet_for(event["to_location"])
    from_wallet = None
    if event.get("from_location") is not None:
        from_wallet = mapping.wallet_for(event["from_location"])

    volume = event.get("volume_uL")
    burn = event.get("burn_uL")
    sample_type = event.get("sample_type")
    owner = event.get("owner")
    consent_ref = event.get("consent_ref")
    agreement_ref = event.get("agreement_ref")
    agreement_hash = event.get("agreement_hash")
    duo_codes = event.get("duo_codes")
    request_event_id = event.get("request_event_id")
    return Operation(
        event_id=event_id,
        op=op_name,
        reason=reason,
        tube=tube,
        volume_uL=None if volume is None else _as_int(volume, "volume_uL"),
        burn_uL=None if burn is None else _as_int(burn, "burn_uL"),
        to_wallet=to_wallet,
        from_wallet=from_wallet,
        sample_type=sample_type if isinstance(sample_type, str) else None,
        owner=owner if isinstance(owner, str) else None,
        consent_ref=consent_ref if isinstance(consent_ref, str) else None,
        children=tuple(children),
        data=_data_ref(event, event_id),
        agreement_ref=agreement_ref if isinstance(agreement_ref, str) else None,
        agreement_hash=agreement_hash if isinstance(agreement_hash, str) else None,
        duo_codes=duo_codes if isinstance(duo_codes, str) else None,
        request_event_id=request_event_id if isinstance(request_event_id, str) else None,
    )


def _data_ref(event: dict, event_id: str) -> DataRef | None:
    raw = event.get("data")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise MappingError(f"{event_id} data must be an object")
    uri = raw.get("data_uri")
    digest = raw.get("content_sha256")
    kind = raw.get("data_type")
    step = raw.get("step")
    if not all(isinstance(value, str) and value for value in (uri, digest, kind, step)):
        raise MappingError(f"{event_id} data needs data_uri, content_sha256, data_type and step")
    licence = raw.get("licence")
    access_level = raw.get("access_level")
    return DataRef(
        data_uri=uri,
        content_hash=digest,
        data_type=kind,
        step=step,
        licence=licence if isinstance(licence, str) else None,
        access_level=access_level if isinstance(access_level, str) else None,
    )
