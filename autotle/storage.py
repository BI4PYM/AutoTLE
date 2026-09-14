from __future__ import annotations

import os
import pickle
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .omm import is_newer, normalize_omm, omm_epoch, omm_identity, parse_int


STATE_VERSION = 2
ALIAS_START = 70000
ALIAS_END = 89999


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="microseconds")


def empty_state() -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "version": STATE_VERSION,
        "created_at": now,
        "updated_at": now,
        "ephemeris": [],
        "aliases": {},
        "sources": {},
        "status": {},
        "timestamps": {},
    }


def _upgrade_state(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        state = empty_state()
        state["ephemeris"] = list(payload)
        return state
    if not isinstance(payload, dict):
        return empty_state()
    if "ephemeris" not in payload:
        values = [value for value in payload.values() if isinstance(value, Mapping)]
        if values and all("EPOCH" in value or "epoch" in value for value in values):
            state = empty_state()
            state["ephemeris"] = values
            return state
    state = empty_state()
    state.update(payload)
    state["version"] = STATE_VERSION
    state["ephemeris"] = list(state.get("ephemeris") or [])
    state["aliases"] = dict(state.get("aliases") or {})
    state["sources"] = dict(state.get("sources") or {})
    state["status"] = dict(state.get("status") or {})
    state["timestamps"] = dict(state.get("timestamps") or {})
    return state


def load_state(path: str | Path) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_state()
    with state_path.open("rb") as handle:
        state = _upgrade_state(pickle.load(handle))
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in state.get("ephemeris", []):
        try:
            record = normalize_omm(raw)
        except Exception:
            continue
        key = omm_identity(record)
        if not key or key in seen:
            continue
        seen.add(key)
        records.append(record)
    state["ephemeris"] = records
    ensure_aliases(state)
    ensure_timestamps(state)
    return state


def save_state(path: str | Path, state: dict[str, Any]) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["version"] = STATE_VERSION
    state["updated_at"] = utc_now_iso()
    handle = tempfile.NamedTemporaryFile(
        mode="wb", delete=False, dir=str(state_path.parent), prefix=state_path.name + ".", suffix=".tmp"
    )
    try:
        pickle.dump(state, handle, protocol=4)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, state_path)
    finally:
        if not handle.closed:
            handle.close()
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def state_index(state: Mapping[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for index, record in enumerate(state.get("ephemeris", [])):
        key = omm_identity(record)
        if key and key not in result:
            result[key] = index
    return result

def needs_alias(norad_cat_id: int | None) -> bool:
    if norad_cat_id is None:
        return False
    if norad_cat_id <= 69999:
        return False
    return not (90000 <= norad_cat_id <= 99999)


def ensure_aliases(state: dict[str, Any]) -> None:
    records = list(state.get("ephemeris") or [])
    existing = {str(key): parse_int(value) for key, value in (state.get("aliases") or {}).items()}
    real_reserved = {
        norad for record in records
        for norad in [parse_int(record.get("NORAD_CAT_ID"))]
        if norad is not None and 70000 <= norad <= 99999
    }
    used = set(real_reserved)
    aliases: dict[str, int] = {}
    for record in records:
        key = omm_identity(record)
        norad = parse_int(record.get("NORAD_CAT_ID"))
        if not key or not needs_alias(norad):
            continue
        current = existing.get(key)
        if current is not None and ALIAS_START <= current <= ALIAS_END and current not in used:
            aliases[key] = current
            used.add(current)
            continue
        candidate = ALIAS_START
        while candidate <= ALIAS_END and candidate in used:
            candidate += 1
        if candidate > ALIAS_END:
            raise RuntimeError("TLE alias range 70000-89999 exhausted")
        aliases[key] = candidate
        used.add(candidate)
    state["aliases"] = aliases


def ensure_timestamps(state: dict[str, Any]) -> None:
    timestamps = state.setdefault("timestamps", {})
    status_map = state.get("status") or {}
    for record in state.get("ephemeris", []):
        key = omm_identity(record)
        if not key:
            continue
        item = timestamps.setdefault(key, {})
        item["orbit_time"] = str(record.get("EPOCH") or "")
        if not item.get("update_time"):
            item["update_time"] = str(status_map.get(key, {}).get("updated_at") or state.get("updated_at") or "")


def catalog_numbers(state: Mapping[str, Any]) -> dict[str, int]:
    aliases = state.get("aliases") or {}
    result: dict[str, int] = {}
    for record in state.get("ephemeris", []):
        key = omm_identity(record)
        norad = parse_int(record.get("NORAD_CAT_ID"))
        if not key or norad is None:
            continue
        result[key] = norad if not needs_alias(norad) else int(aliases[key])
    return result


def merge_fetched(
    state: dict[str, Any],
    fetched: list[dict[str, Any]],
    source: Mapping[str, Any] | None = None,
    identity_hint: str | None = None,
) -> dict[str, Any]:
    state.setdefault("ephemeris", [])
    state.setdefault("aliases", {})
    state.setdefault("sources", {})
    state.setdefault("status", {})
    state.setdefault("timestamps", {})
    index = state_index(state)
    summary = {"added": 0, "updated": 0, "stale": 0, "same": 0, "skipped": 0, "keys": [], "details": []}
    single_hint = identity_hint if len(fetched) == 1 else None

    for raw in fetched:
        try:
            record = normalize_omm(raw)
        except Exception:
            summary["skipped"] += 1
            continue
        key = single_hint or omm_identity(record)
        if not key:
            summary["skipped"] += 1
            continue
        existing_index = index.get(key)
        if existing_index is None:
            object_id = str(record.get("OBJECT_ID") or "").strip().upper()
            object_name = str(record.get("OBJECT_NAME") or "").strip().upper()
            for existing_key, candidate_index in index.items():
                candidate = state["ephemeris"][candidate_index]
                if object_id and str(candidate.get("OBJECT_ID") or "").strip().upper() == object_id:
                    key = existing_key
                    existing_index = candidate_index
                    break
                if (
                    object_name
                    and candidate.get("NORAD_CAT_ID") is None
                    and str(candidate.get("OBJECT_NAME") or "").strip().upper() == object_name
                ):
                    key = existing_key
                    existing_index = candidate_index
                    break
        summary["keys"].append(key)
        accepted = False
        if existing_index is None:
            state["ephemeris"].append(record)
            index[key] = len(state["ephemeris"]) - 1
            summary["added"] += 1
            summary["details"].append({"key": key, "status": "added", "record": record})
            accepted = True
        else:
            old = state["ephemeris"][existing_index]
            old_epoch = omm_epoch(old)
            new_epoch = omm_epoch(record)
            if is_newer(record, old):
                state["ephemeris"][existing_index] = record
                summary["updated"] += 1
                summary["details"].append({"key": key, "status": "updated", "record": record, "old": old})
                accepted = True
            elif new_epoch is not None and old_epoch is not None and new_epoch == old_epoch:
                summary["same"] += 1
                summary["details"].append({"key": key, "status": "same", "record": record, "old": old})
            else:
                summary["stale"] += 1
                summary["details"].append({"key": key, "status": "stale", "record": record, "old": old})
        if source is not None:
            state["sources"][key] = dict(source)
        if accepted:
            pass

    ensure_aliases(state)
    state["updated_at"] = utc_now_iso()
    return summary
