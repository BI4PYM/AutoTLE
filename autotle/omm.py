from __future__ import annotations

import csv
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


OMM_FIELD_ORDER = [
    "CCSDS_OMM_VERS", "COMMENT", "CREATION_DATE", "ORIGINATOR", "OBJECT_NAME",
    "OBJECT_ID", "CENTER_NAME", "REF_FRAME", "TIME_SYSTEM", "MEAN_ELEMENT_THEORY",
    "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY", "EPHEMERIS_TYPE", "CLASSIFICATION_TYPE",
    "NORAD_CAT_ID", "ELEMENT_SET_NO", "REV_AT_EPOCH", "BSTAR", "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
]

FLOAT_FIELDS = {
    "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
    "ARG_OF_PERICENTER", "MEAN_ANOMALY", "BSTAR", "MEAN_MOTION_DOT",
    "MEAN_MOTION_DDOT",
}
INT_FIELDS = {"NORAD_CAT_ID", "EPHEMERIS_TYPE", "ELEMENT_SET_NO", "REV_AT_EPOCH"}
STRING_FIELDS = {
    "CCSDS_OMM_VERS", "COMMENT", "CREATION_DATE", "ORIGINATOR", "OBJECT_NAME",
    "OBJECT_ID", "CENTER_NAME", "REF_FRAME", "TIME_SYSTEM",
    "MEAN_ELEMENT_THEORY", "EPOCH", "CLASSIFICATION_TYPE",
}
DEFAULT_OMM_VALUES = {
    "CCSDS_OMM_VERS": "2.0", "CREATION_DATE": "", "ORIGINATOR": "",
    "CENTER_NAME": "EARTH", "REF_FRAME": "TEME", "TIME_SYSTEM": "UTC",
    "MEAN_ELEMENT_THEORY": "SGP/SGP4", "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U", "ELEMENT_SET_NO": 999, "REV_AT_EPOCH": 0,
}
METADATA_XML_FIELDS = {
    "CCSDS_OMM_VERS", "COMMENT", "CREATION_DATE", "ORIGINATOR", "OBJECT_NAME",
    "OBJECT_ID", "CENTER_NAME", "REF_FRAME", "TIME_SYSTEM",
    "MEAN_ELEMENT_THEORY",
}


class OMMParseError(ValueError):
    """Raised when a source cannot be parsed as OMM data."""


def _is_missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def parse_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return float(value)
    text = str(value).strip()
    if text.lower() in {"null", "none", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    if _is_missing(value) or isinstance(value, bool):
        return int(value) if isinstance(value, bool) else None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.lower() in {"null", "none"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_epoch_value(value: Any) -> datetime | None:
    if _is_missing(value):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def epoch_to_iso(value: Any) -> str | None:
    dt = parse_epoch_value(value)
    return None if dt is None else dt.isoformat(timespec="microseconds")


def normalize_omm(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise OMMParseError("OMM record is not a mapping")
    result: dict[str, Any] = {}
    for key, value in raw.items():
        if key is None:
            continue
        key_text = str(key).strip()
        if not key_text:
            continue
        canonical = key_text if key_text.startswith("_") else key_text.upper()
        result[canonical] = value
    for key, value in DEFAULT_OMM_VALUES.items():
        if key not in result or _is_missing(result.get(key)):
            result[key] = value
    for key in FLOAT_FIELDS:
        if key in result:
            parsed = parse_float(result[key])
            if parsed is not None:
                result[key] = parsed
    for key in INT_FIELDS:
        if key in result:
            parsed = parse_int(result[key])
            if parsed is not None:
                result[key] = parsed
    for key in STRING_FIELDS:
        if key in result and not _is_missing(result[key]):
            result[key] = str(result[key]).strip()
    if "EPOCH" in result:
        normalized_epoch = epoch_to_iso(result["EPOCH"])
        if normalized_epoch:
            result["EPOCH"] = normalized_epoch
    if result.get("OBJECT_NAME"):
        result["OBJECT_NAME"] = re.sub(r"\s+", " ", str(result["OBJECT_NAME"])).strip()
    return result


def normalize_omms(raw: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for item in raw:
        normalized = normalize_omm(item)
        if record_has_elements(normalized):
            records.append(normalized)
    return records


def record_has_elements(record: Mapping[str, Any]) -> bool:
    return any(not _is_missing(record.get(key)) for key in
               ("EPOCH", "MEAN_MOTION", "NORAD_CAT_ID", "OBJECT_NAME"))


def omm_identity(record: Mapping[str, Any]) -> str | None:
    norad = parse_int(record.get("NORAD_CAT_ID"))
    if norad is not None:
        return f"norad:{norad}"
    object_id = str(record.get("OBJECT_ID") or "").strip().upper()
    if object_id:
        return f"object:{object_id}"
    name = str(record.get("OBJECT_NAME") or "").strip().upper()
    return f"name:{name}" if name else None


def omm_epoch(record: Mapping[str, Any]) -> datetime | None:
    return parse_epoch_value(record.get("EPOCH"))


def is_newer(new: Mapping[str, Any], old: Mapping[str, Any]) -> bool:
    new_epoch = omm_epoch(new)
    old_epoch = omm_epoch(old)
    if new_epoch is None:
        return False
    return old_epoch is None or new_epoch > old_epoch

def parse_json_omms(text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise OMMParseError(f"invalid JSON: {exc}") from exc
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, Mapping):
        if isinstance(payload.get("data"), list):
            records = payload["data"]
        elif isinstance(payload.get("results"), list):
            records = payload["results"]
        elif isinstance(payload.get("ephemeris"), list):
            records = payload["ephemeris"]
        else:
            records = [payload]
    else:
        raise OMMParseError("JSON payload is neither an object nor a list")
    return normalize_omms([item for item in records if isinstance(item, Mapping)])


def parse_kvn_omms(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        if key == "CCSDS_OMM_VERS" and current.get("CCSDS_OMM_VERS") is not None:
            records.append(normalize_omm(current))
            current = {}
        current[key] = value.strip()
    if current:
        records.append(normalize_omm(current))
    return [record for record in records if record_has_elements(record)]


def parse_csv_omms(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        upper = line.upper()
        if any(marker in upper for marker in ("OBJECT_NAME", "NORAD_CAT_ID", "CCSDS_OMM_VERS")):
            header_index = index
            break
    if header_index is None:
        raise OMMParseError("CSV header not found")
    reader = csv.DictReader(lines[header_index:])
    records: list[dict[str, Any]] = []
    for row in reader:
        if any((value or "").strip() for value in row.values()):
            records.append(normalize_omm(row))
    return [record for record in records if record_has_elements(record)]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].upper()


def _xml_leaves(element: ET.Element) -> dict[str, Any]:
    leaves: dict[str, Any] = {}
    def walk(node: ET.Element) -> None:
        children = list(node)
        if not children:
            value = (node.text or "").strip()
            if value:
                key = _local_name(node.tag)
                if key in leaves:
                    previous = leaves[key]
                    if isinstance(previous, list):
                        previous.append(value)
                    else:
                        leaves[key] = [previous, value]
                else:
                    leaves[key] = value
            return
        for child in children:
            walk(child)
    walk(element)
    return leaves


def parse_xml_omms(text: str) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise OMMParseError(f"invalid XML: {exc}") from exc
    candidates = [element for element in root.iter()
                  if _local_name(element.tag) in {"SEGMENT", "OMM", "MEAN-ELEMENTS-MESSAGE"}]
    if not candidates:
        candidates = [root]
    else:
        candidates = [
            candidate for candidate in candidates
            if not any(
                candidate is not other and any(descendant is candidate for descendant in other.iter())
                for other in candidates
            )
        ]
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        leaves = _xml_leaves(candidate)
        leaves = {key: value for key, value in leaves.items()
                  if key not in {"NDM", "BODY", "SEGMENT"}}
        if leaves:
            records.append(normalize_omm(leaves))
    return [record for record in records if record_has_elements(record)]


def parse_omm_text(text: str, source_format: str) -> list[dict[str, Any]]:
    fmt = source_format.upper().replace("_", "-")
    if fmt in {"JSON", "JSON-PRETTY"}:
        return parse_json_omms(text)
    if fmt == "KVN":
        return parse_kvn_omms(text)
    if fmt == "CSV":
        return parse_csv_omms(text)
    if fmt == "XML":
        return parse_xml_omms(text)
    if fmt in {"TLE", "3LE", "2LE"}:
        from .tle import parse_tle_text
        return parse_tle_text(text)
    raise OMMParseError(f"unsupported OMM format: {source_format}")

def _format_scalar(value: Any) -> str:
    if _is_missing(value):
        return ""
    if isinstance(value, float):
        return "0" if value == 0 else repr(value)
    return str(value)


def public_omm(record: Mapping[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in OMM_FIELD_ORDER:
        value = record.get(key)
        if not key.startswith("_") and not _is_missing(value):
            ordered[key] = value
    for key in sorted(record):
        if key.startswith("_") or key in ordered or key in OMM_FIELD_ORDER:
            continue
        value = record[key]
        if not _is_missing(value):
            ordered[key] = value
    return ordered


def render_json_omms(records: Iterable[Mapping[str, Any]], pretty: bool = True) -> str:
    payload = [public_omm(record) for record in records]
    if pretty:
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"


def render_kvn_omms(records: Iterable[Mapping[str, Any]]) -> str:
    blocks: list[str] = []
    for record in records:
        lines = [f"{key:<14} = {_format_scalar(value)}"
                 for key, value in public_omm(record).items()]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def render_csv_omms(records: Iterable[Mapping[str, Any]]) -> str:
    public_records = [public_omm(record) for record in records]
    fieldnames: list[str] = []
    for record in public_records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["OBJECT_NAME", "OBJECT_ID", "EPOCH", "NORAD_CAT_ID"]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in public_records:
        writer.writerow({key: _format_scalar(record.get(key)) for key in fieldnames})
    return output.getvalue()


def _append_xml_group(parent: ET.Element, tag: str, keys: list[str], record: Mapping[str, Any]) -> None:
    values = {key: record.get(key) for key in keys if not _is_missing(record.get(key))}
    if not values:
        return
    group = ET.SubElement(parent, tag)
    for key, value in values.items():
        child = ET.SubElement(group, key)
        child.text = _format_scalar(value)


def _indent_xml(element: ET.Element, space: str = "  ", level: int = 0) -> None:
    if hasattr(ET, "indent"):
        ET.indent(element, space=space)
        return
    indentation = "\n" + level * space
    if len(element):
        if not element.text or not element.text.strip():
            element.text = indentation + space
        for child in element:
            _indent_xml(child, space, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = indentation
    if level and (not element.tail or not element.tail.strip()):
        element.tail = indentation


def render_xml_omms(records: Iterable[Mapping[str, Any]]) -> str:
    root = ET.Element("ndm")
    body = ET.SubElement(root, "body")
    mean_keys = [
        "EPOCH", "MEAN_MOTION", "ECCENTRICITY", "INCLINATION", "RA_OF_ASC_NODE",
        "ARG_OF_PERICENTER", "MEAN_ANOMALY", "GM", "MASS", "SOLAR_RAD_AREA",
        "SOLAR_RAD_COEFF", "DRAG_AREA", "DRAG_COEFF",
    ]
    tle_keys = [
        "EPHEMERIS_TYPE", "CLASSIFICATION_TYPE", "NORAD_CAT_ID", "ELEMENT_SET_NO",
        "REV_AT_EPOCH", "BSTAR", "MEAN_MOTION_DOT", "MEAN_MOTION_DDOT",
    ]
    for record in records:
        public = public_omm(record)
        segment = ET.SubElement(body, "segment")
        metadata = ET.SubElement(segment, "metadata")
        for key in [field for field in OMM_FIELD_ORDER if field in METADATA_XML_FIELDS]:
            if not _is_missing(public.get(key)):
                child = ET.SubElement(metadata, key)
                child.text = _format_scalar(public[key])
        _append_xml_group(segment, "meanElements", mean_keys, public)
        _append_xml_group(segment, "tleParameters", tle_keys, public)
    _indent_xml(root, space="  ")
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"
