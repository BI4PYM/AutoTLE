from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


VALID_FORMATS = {"TLE", "3LE", "2LE", "JSON", "JSON-PRETTY", "KVN", "CSV", "XML"}
FORMAT_ALIASES = {"OMM": "JSON", "OMM-JSON": "JSON", "OMM_JSON": "JSON", "TXT": "TLE"}
DEFAULT_LEGACY_FORMATS = ("TLE",)
DEFAULT_NEW_FORMATS = ("TLE", "JSON")
VALID_QUERIES = {"CATNR", "NAME", "INTDES", "GROUP", "SPECIAL", "SATID", "SAT_ID"}
VALID_SOURCES = {"celestrak", "satnogs", "localtle", "localjson", "local"}


@dataclass(frozen=True)
class SatelliteSpec:
    id: str
    name: str
    query: str
    formats: tuple[str, ...]
    sources: tuple[str, ...] | None = None
    index: int = 0


@dataclass
class SatelliteListConfig:
    path: Path
    stem: str
    formats: tuple[str, ...]
    satellites: list[SatelliteSpec] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def source_name(self) -> str:
        return self.path.name


def normalize_format(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper().replace(" ", "")
    text = FORMAT_ALIASES.get(text, text)
    return text if text in VALID_FORMATS else None


def parse_output_formats(value: Any, default: Iterable[str] = DEFAULT_NEW_FORMATS) -> tuple[str, ...]:
    if value is None:
        raw_values: list[Any] = list(default)
    elif isinstance(value, str):
        raw_values = [part for part in value.replace("|", ",").replace(";", ",").split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raw_values = [value]
    result: list[str] = []
    for item in raw_values:
        normalized = normalize_format(item)
        if normalized and normalized not in result:
            result.append(normalized)
    return tuple(result or default)

def _parse_sources(value: Any) -> tuple[str, ...] | None:
    if value is None:
        return None
    values = value if isinstance(value, (list, tuple)) else str(value).replace("|", ",").split(",")
    result: list[str] = []
    for item in values:
        source = str(item).strip().lower()
        if source in VALID_SOURCES and source not in result:
            result.append(source)
    return tuple(result) if result else None


def _parse_spec(item: Any, default_formats: tuple[str, ...], index: int) -> SatelliteSpec:
    if isinstance(item, (list, tuple)):
        if len(item) < 3:
            raise ValueError("legacy satellite entries need [id, name, query]")
        satellite_id = str(item[0]).strip()
        name = str(item[1]).strip()
        query = str(item[2]).strip().upper()
        formats = parse_output_formats(item[3], default_formats) if len(item) >= 4 else default_formats
        sources = _parse_sources(item[4] if len(item) >= 5 else None)
    elif isinstance(item, Mapping):
        satellite_id = str(
            item.get("id", item.get("norad_cat_id", item.get("identifier", item.get("sat_id", ""))))
        ).strip()
        name = str(item.get("name", item.get("object_name", ""))).strip()
        query = str(item.get("query", item.get("query_type", item.get("type", "CATNR")))).strip().upper()
        formats = parse_output_formats(item.get("formats", item.get("format")), default_formats)
        sources = _parse_sources(item.get("sources", item.get("source")))
    else:
        raise ValueError(f"unsupported satellite entry: {item!r}")

    if not satellite_id:
        raise ValueError("satellite entry is missing an identifier")
    if not query or query not in VALID_QUERIES:
        raise ValueError(f"unsupported query type: {query!r}")
    return SatelliteSpec(satellite_id, name, query, formats, sources, index)


def parse_satellite_list(payload: Any, path: Path) -> SatelliteListConfig:
    if isinstance(payload, list):
        default_formats = DEFAULT_LEGACY_FORMATS
        explicit_global = False
        raw_entries = payload
        raw = {"satellites": payload}
    elif isinstance(payload, Mapping):
        raw = dict(payload)
        raw_entries = payload.get("satellites", payload.get("items", payload.get("list")))
        if raw_entries is None:
            raise ValueError("satellite list object needs a 'satellites' array")
        if not isinstance(raw_entries, list):
            raise ValueError("'satellites' must be an array")
        format_value = payload.get("formats", payload.get("output_formats"))
        explicit_global = format_value is not None
        default_formats = parse_output_formats(format_value, DEFAULT_NEW_FORMATS)
    else:
        raise ValueError("satellite list must be a JSON array or object")

    satellites = [_parse_spec(item, default_formats, index) for index, item in enumerate(raw_entries)]
    if not satellites:
        raise ValueError("satellite list is empty")
    derived_formats: list[str] = []
    for satellite in satellites:
        for source_format in satellite.formats:
            if source_format not in derived_formats:
                derived_formats.append(source_format)
    effective_formats = default_formats if explicit_global else tuple(derived_formats or default_formats)
    return SatelliteListConfig(
        path=path,
        stem=path.stem,
        formats=effective_formats,
        satellites=satellites,
        raw=raw,
    )

def load_satellite_list(path: str | Path) -> SatelliteListConfig:
    list_path = Path(path)
    with list_path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)
    return parse_satellite_list(payload, list_path)


def discover_satellite_lists(project_root: str | Path) -> list[Path]:
    root = Path(project_root)
    folder = root / "satellitelists"
    paths = sorted(folder.glob("*.json")) if folder.exists() else []
    if paths:
        return paths
    legacy = root / "satelist.json"
    return [legacy] if legacy.exists() else []
