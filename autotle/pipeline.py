from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from .config import SatelliteListConfig, SatelliteSpec, discover_satellite_lists, load_satellite_list
from .omm import omm_identity, parse_int, render_csv_omms, render_json_omms, render_kvn_omms, render_xml_omms
from .sources import FetchResult, fetch_for_spec
from .storage import catalog_numbers, ensure_aliases, load_state, merge_fetched, save_state, state_index
from .tle import render_tle


@dataclass
class PipelineOptions:
    project_root: Path
    state_path: Path
    output_dir: Path
    list_paths: list[Path] | None = None
    sources: tuple[str, ...] = ("celestrak", "satnogs", "localtle", "localjson")
    celestrak_formats: tuple[str, ...] = ("JSON", "KVN", "CSV", "XML", "TLE")
    timeout: float = 20.0
    retries: int = 2
    proxy: str | None = None
    offline: bool = False
    dry_run: bool = False
    limit: int | None = None
    quiet: bool = True

    @classmethod
    def from_root(cls, project_root: str | Path) -> "PipelineOptions":
        root = Path(project_root).resolve()
        env_sources = os.environ.get("AUTOTLE_SOURCES", "celestrak,satnogs,localtle,localjson")
        env_formats = os.environ.get("AUTOTLE_CELESTRAK_FORMATS", "JSON,KVN,CSV,XML,TLE")
        return cls(
            project_root=root,
            state_path=root / os.environ.get("AUTOTLE_STATE", "satellites.pkl"),
            output_dir=root / os.environ.get("AUTOTLE_OUTPUT_DIR", "satellites"),
            sources=tuple(item.strip().lower() for item in env_sources.split(",") if item.strip()),
            celestrak_formats=tuple(item.strip().upper() for item in env_formats.split(",") if item.strip()),
            timeout=float(os.environ.get("AUTOTLE_TIMEOUT", "20")),
            retries=int(os.environ.get("AUTOTLE_RETRIES", "2")),
            proxy=os.environ.get("AUTOTLE_PROXY") or None,
            offline=os.environ.get("AUTOTLE_OFFLINE", "").lower() in {"1", "true", "yes"},
            quiet=os.environ.get("AUTOTLE_QUIET", "").lower() in {"1", "true", "yes"},
        )


@dataclass
class ListRunReport:
    config: SatelliteListConfig
    keys: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    log_entries: list[dict[str, str]] = field(default_factory=list)
    added: int = 0
    updated: int = 0
    stale: int = 0
    same: int = 0
    skipped: int = 0


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _append_key(keys: list[str], key: str | None) -> None:
    if key and key not in keys:
        keys.append(key)


def _hint_for_spec(spec: SatelliteSpec) -> str | None:
    if spec.query == "CATNR" and spec.id.isdigit():
        return f"norad:{int(spec.id)}"
    return None


def _find_existing_key(state: Mapping[str, Any], spec: SatelliteSpec) -> str | None:
    index = state_index(state)
    hint = _hint_for_spec(spec)
    if hint and hint in index:
        return hint
    wanted_id = spec.id.strip().upper()
    name_query = spec.id if spec.query == "NAME" else spec.name
    wanted_name = re.sub(r"\s+", " ", name_query).strip().upper()
    for key, record in zip(index.keys(), state.get("ephemeris", [])):
        if spec.query in {"SATID", "SAT_ID"}:
            source = (state.get("sources") or {}).get(key, {})
            if str(source.get("_SAT_ID") or "").strip() == spec.id:
                return key
        actual_object_id = str(record.get("OBJECT_ID") or "").upper()
        if spec.query == "INTDES" and wanted_id and actual_object_id.startswith(wanted_id):
            return key
        if wanted_id and actual_object_id == wanted_id:
            return key
        if wanted_name:
            actual = re.sub(r"\s+", " ", str(record.get("OBJECT_NAME") or "")).strip().upper()
            if wanted_name == actual or wanted_name in actual:
                return key
    return None


def _records_for_keys(state: Mapping[str, Any], keys: Iterable[str]) -> list[dict[str, Any]]:
    index = state_index(state)
    records: list[dict[str, Any]] = []
    for key in keys:
        position = index.get(key)
        if position is not None:
            records.append(state["ephemeris"][position])
    return records


def _names_for_config(config: SatelliteListConfig, state: Mapping[str, Any], keys: Iterable[str]) -> dict[str, str]:
    names: dict[str, str] = {}
    for spec in config.satellites:
        if not spec.name:
            continue
        key = _hint_for_spec(spec) or _find_existing_key(state, spec)
        if key and key in keys:
            names[key] = spec.name
    return names


def _write_formats(
    config: SatelliteListConfig,
    state: Mapping[str, Any],
    keys: list[str],
    options: PipelineOptions,
) -> list[str]:
    records = _records_for_keys(state, keys)
    catalog = catalog_numbers(state)
    names = _names_for_config(config, state, keys)
    formats = set(config.formats)
    outputs: list[str] = []
    output_dir = options.output_dir
    root_tle_written = False

    if {"TLE", "3LE"} & formats:
        path = output_dir / f"{config.stem}.txt"
        tle_text = render_tle(records, catalog, names, include_name=True)
        _atomic_write(path, tle_text)
        outputs.append(str(path))
        root_copy = options.project_root / path.name
        if root_copy.resolve() != path.resolve():
            _atomic_write(root_copy, tle_text)
            outputs.append(str(root_copy))
        root_tle_written = True
    if "2LE" in formats:
        path = output_dir / f"{config.stem}.2le.txt"
        tle_text = render_tle(records, catalog, names, include_name=False)
        _atomic_write(path, tle_text)
        outputs.append(str(path))
        root_copy = options.project_root / path.name
        if root_copy.resolve() != path.resolve():
            _atomic_write(root_copy, tle_text)
            outputs.append(str(root_copy))
    if not root_tle_written:
        root_copy = options.project_root / f"{config.stem}.txt"
        _atomic_write(root_copy, render_tle(records, catalog, names, include_name=True))
        outputs.append(str(root_copy))
    if {"JSON", "JSON-PRETTY"} & formats:
        path = output_dir / f"{config.stem}.json"
        _atomic_write(path, render_json_omms(records, pretty=True))
        outputs.append(str(path))
    if "KVN" in formats:
        path = output_dir / f"{config.stem}.kvn"
        _atomic_write(path, render_kvn_omms(records))
        outputs.append(str(path))
    if "CSV" in formats:
        path = output_dir / f"{config.stem}.csv"
        _atomic_write(path, render_csv_omms(records))
        outputs.append(str(path))
    if "XML" in formats:
        path = output_dir / f"{config.stem}.xml"
        _atomic_write(path, render_xml_omms(records))
        outputs.append(str(path))
    return outputs


def _status_text(status: str) -> str:
    return {
        "added": "成功新增",
        "updated": "成功更新",
        "same": "星历源与缓存一致",
        "stale": "星历源比缓存更旧",
        "skipped": "失败（星历无效或缺少 NORAD_CAT_ID）",
    }.get(status, status)


def _log_entry(list_name: str, spec: SatelliteSpec, record: Mapping[str, Any] | None, source: str, status: str, detail: str = "", key: str | None = None, time_value: str | None = None) -> dict[str, str]:
    norad = record.get("NORAD_CAT_ID") if record else None
    object_id = record.get("OBJECT_ID") if record else None
    name = record.get("OBJECT_NAME") if record else None
    return {
        "time": time_value or datetime.now().astimezone().isoformat(timespec="seconds"),
        "key": key or (omm_identity(record) if record else "") or "",
        "list": list_name,
        "id": str(norad or object_id or spec.id),
        "name": str(name or spec.name or spec.id),
        "source": source or "-",
        "status": status,
        "detail": detail,
    }


@dataclass
class CachedSatellite:
    raw_status: str
    display_status: str
    source: str
    source_format: str
    source_url: str
    log_time: str = ""


@dataclass
class RunFetchCache:
    request_results: dict[str, FetchResult] = field(default_factory=dict)
    records: dict[str, CachedSatellite] = field(default_factory=dict)


def _request_cache_key(spec: SatelliteSpec, sources: Iterable[str]) -> str:
    return "|".join(sources) + "::" + spec.query.upper() + "::" + spec.id


def _cached_result_from_keys(
    state: Mapping[str, Any],
    keys: list[str],
    cache: RunFetchCache,
) -> tuple[FetchResult, dict[str, CachedSatellite]] | None:
    index = state_index(state)
    records: list[dict[str, Any]] = []
    metadata: list[CachedSatellite] = []
    selected: list[str] = []
    for key in keys:
        cached = cache.records.get(key)
        position = index.get(key)
        if cached is None or position is None:
            continue
        records.append(state["ephemeris"][position])
        metadata.append(cached)
        selected.append(key)
    if not records:
        return None
    identities = {(item.source, item.source_format, item.source_url) for item in metadata}
    if len(identities) == 1:
        source, source_format, source_url = next(iter(identities))
    else:
        source, source_format, source_url = "run-cache", "", ""
    result = FetchResult(records, source or "run-cache", source_url, source_format)
    return result, {key: cache.records[key] for key in selected}


def _find_cached_result(
    state: Mapping[str, Any],
    spec: SatelliteSpec,
    cache: RunFetchCache,
) -> tuple[FetchResult, dict[str, CachedSatellite]] | None:
    if not cache.records:
        return None
    index = state_index(state)
    if spec.query == "CATNR" and spec.id.isdigit():
        key = f"norad:{int(spec.id)}"
        return _cached_result_from_keys(state, [key], cache) if key in cache.records else None
    if spec.query == "INTDES":
        wanted = re.sub(r"[^A-Z0-9]", "", spec.id.upper())
        keys = []
        for key in cache.records:
            position = index.get(key)
            if position is None:
                continue
            record = state["ephemeris"][position]
            object_id = re.sub(r"[^A-Z0-9]", "", str(record.get("OBJECT_ID") or "").upper())
            if wanted and object_id.startswith(wanted):
                keys.append(key)
        return _cached_result_from_keys(state, keys, cache)
    if spec.query == "NAME":
        wanted = re.sub(r"\s+", " ", spec.id).strip().upper()
        keys = []
        for key in cache.records:
            position = index.get(key)
            if position is None:
                continue
            record = state["ephemeris"][position]
            actual = re.sub(r"\s+", " ", str(record.get("OBJECT_NAME") or "")).strip().upper()
            if wanted and (wanted == actual or wanted in actual or actual in wanted):
                keys.append(key)
        return _cached_result_from_keys(state, keys, cache)
    if spec.query in {"SATID", "SAT_ID"}:
        keys = []
        for key in cache.records:
            cached = cache.records[key]
            if cached.source_url and spec.id in cached.source_url:
                keys.append(key)
        return _cached_result_from_keys(state, keys, cache)
    return None


def _bump_report_status(report: ListRunReport, raw_status: str) -> None:
    if raw_status == "added":
        report.added += 1
    elif raw_status == "updated":
        report.updated += 1
    elif raw_status == "same":
        report.same += 1
    elif raw_status == "stale":
        report.stale += 1
    elif raw_status == "skipped":
        report.skipped += 1


def _cached_statuses_for_result(
    state: Mapping[str, Any],
    result: FetchResult,
    cache: RunFetchCache,
) -> dict[str, CachedSatellite] | None:
    keys = [omm_identity(record) or "" for record in result.records]
    if not keys or any(not key or key not in cache.records for key in keys):
        return None
    return {key: cache.records[key] for key in keys}


def _process_list(options: PipelineOptions, state: dict[str, Any], list_path: Path, cache: RunFetchCache) -> ListRunReport:
    config = load_satellite_list(list_path)
    if options.limit is not None:
        config.satellites = config.satellites[:options.limit]
    report = ListRunReport(config=config)
    local_paths = [
        options.project_root / "localTLE.txt",
        options.project_root / "localJSON.json",
    ]
    total = len(config.satellites)
    for spec_index, spec in enumerate(config.satellites, 1):
        log_start = len(report.log_entries)
        sources = spec.sources or options.sources
        if options.offline:
            sources = ("localtle", "localjson")
        cache_key = _request_cache_key(spec, sources)
        cached_statuses: dict[str, CachedSatellite] | None = None
        result: FetchResult | None = None

        cached_probe = _find_cached_result(state, spec, cache)
        if cached_probe is not None:
            result, cached_statuses = cached_probe
        else:
            result = cache.request_results.get(cache_key)
            if result is None:
                if not options.quiet:
                    label = spec.name or spec.id
                    print(f"[{config.source_name} {spec_index}/{total}] {spec.id} {label} | querying...", flush=True)
                result = fetch_for_spec(
                    spec,
                    sources,
                    options.celestrak_formats,
                    options.timeout,
                    options.retries,
                    options.proxy,
                    local_paths,
                )
                cache.request_results[cache_key] = result
            else:
                cached_statuses = _cached_statuses_for_result(state, result, cache)

        source_label = result.source + (f":{result.format}" if result.format else "")
        hint = _hint_for_spec(spec)
        if result.records and cached_statuses is not None:
            index = state_index(state)
            for key, cached in cached_statuses.items():
                position = index.get(key)
                if position is None:
                    continue
                record = state["ephemeris"][position]
                report.log_entries.append(
                    _log_entry(
                        config.source_name,
                        spec,
                        record,
                        cached.source + (f":{cached.source_format}" if cached.source_format else ""),
                        cached.display_status,
                        key=key,
                        time_value=cached.log_time,
                    )
                )
                _append_key(report.keys, key)
                _bump_report_status(report, cached.raw_status)
        elif result.records:
            summary = merge_fetched(
                state,
                result.records,
                {
                    "_SOURCE": result.source,
                    "_SOURCE_URL": result.url,
                    "_SOURCE_FORMAT": result.format,
                },
                identity_hint=hint,
            )
            for detail in summary["details"]:
                entry = _log_entry(
                    config.source_name,
                    spec,
                    detail["record"],
                    source_label,
                    _status_text(detail["status"]),
                    key=detail["key"],
                )
                report.log_entries.append(entry)
                cache.records[detail["key"]] = CachedSatellite(
                    raw_status=detail["status"],
                    display_status=_status_text(detail["status"]),
                    source=result.source,
                    source_format=result.format,
                    source_url=result.url,
                    log_time=entry["time"],
                )
            for key in summary["keys"]:
                _append_key(report.keys, key)
            report.added += summary["added"]
            report.updated += summary["updated"]
            report.stale += summary["stale"]
            report.same += summary.get("same", 0)
            report.skipped += summary["skipped"]
        else:
            cached = _find_existing_key(state, spec)
            status = "失败（使用缓存）" if cached else "失败"
            report.log_entries.append(_log_entry(config.source_name, spec, None, source_label, status, result.error or "", key=cached))
            if cached:
                _append_key(report.keys, cached)
                report.errors.append(f"{spec.id}: {result.error}; using cached data")
            else:
                report.errors.append(f"{spec.id}: {result.error}")
        cached = _find_existing_key(state, spec)
        if cached:
            _append_key(report.keys, cached)
        if not options.quiet:
            for entry in report.log_entries[log_start:]:
                detail = f" | {entry.get('detail')}" if entry.get("detail") else ""
                print(
                    f"[{config.source_name} {spec_index}/{total}] "
                    f"{entry.get('id', '')} {entry.get('name', '')} | "
                    f"{entry.get('source', '-')} | {entry.get('status', '')}{detail}",
                    flush=True,
                )
    return report

_STATUS_PRIORITY = {
    "成功新增": 6,
    "成功更新": 5,
    "星历源与缓存一致": 4,
    "星历源比缓存更旧": 3,
    "失败（使用缓存）": 2,
    "失败": 1,
    "未处理": 0,
}


def _update_status(state: dict[str, Any], previous_statuses: Mapping[str, str], entries: list[dict[str, str]], run_started: str) -> None:
    best: dict[str, str] = {}
    best_entries: dict[str, dict[str, str]] = {}
    for entry in entries:
        key = entry.get("key") or ""
        status = entry.get("status") or "未处理"
        if not key:
            continue
        if key not in best or _STATUS_PRIORITY.get(status, 1) > _STATUS_PRIORITY.get(best[key], 1):
            best[key] = status
            best_entries[key] = entry
    status_map = state.setdefault("status", {})
    timestamps = state.setdefault("timestamps", {})
    for record in state.get("ephemeris", []):
        key = omm_identity(record)
        if not key:
            continue
        prior = previous_statuses.get(key, status_map.get(key, {}).get("current_status", "首次记录"))
        current = best.get(key, "未处理")
        old = status_map.get(key, {})
        old_timestamp = timestamps.get(key, {})
        entry = best_entries.get(key)
        update_time = str(old_timestamp.get("update_time") or old.get("updated_at") or "")
        if entry and current in {"成功新增", "成功更新"}:
            update_time = str(entry.get("time") or run_started)
        timestamps[key] = {
            "update_time": update_time,
            "orbit_time": str(record.get("EPOCH") or ""),
        }
        status_map[key] = {
            "previous_status": prior,
            "current_status": current,
            "updated_at": run_started if key in best else old.get("updated_at", ""),
        }


def _write_status_md(path: Path, state: Mapping[str, Any], run_started: str) -> None:
    sources = state.get("sources") or {}
    status_map = state.get("status") or {}
    timestamps = state.get("timestamps") or {}

    def clean(value: Any) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ").strip()

    lines = [
        "# AutoTLE Satellite Cache Status",
        "",
        f"- generated: {run_started}",
        "- order: satellites.pkl ephemeris insertion order",
        "",
        "| 卫星编号 | 卫星名称 | 星历来源 | 更新时间 | 定轨时间 (EPOCH) | 上一次更新状态 | 这一次更新状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    for record in state.get("ephemeris", []):
        key = omm_identity(record) or ""
        source_meta = sources.get(key, {})
        source = str(source_meta.get("_SOURCE") or "-")
        source_format = str(source_meta.get("_SOURCE_FORMAT") or "").strip()
        if source_format:
            source = f"{source}:{source_format}"
        status = status_map.get(key, {})
        lines.append("| " + " | ".join([
            clean(record.get("NORAD_CAT_ID") or record.get("OBJECT_ID")),
            clean(record.get("OBJECT_NAME")),
            clean(source),
            clean(timestamps.get(key, {}).get("update_time")),
            clean(record.get("EPOCH")),
            clean(status.get("previous_status") or "首次记录"),
            clean(status.get("current_status") or "未处理"),
        ]) + " |")
    _atomic_write(path, "\n".join(lines) + "\n")


def _summary_from_reports(state: Mapping[str, Any] | None, reports: list[ListRunReport]) -> dict[str, int]:
    return {
        "lists": len(reports),
        "satellites": len(state.get("ephemeris", [])) if state else 0,
        "added": sum(report.added for report in reports),
        "updated": sum(report.updated for report in reports),
        "stale": sum(report.stale for report in reports),
        "same": sum(report.same for report in reports),
        "skipped": sum(report.skipped for report in reports),
        "errors": sum(len(report.errors) for report in reports),
    }


def _write_run_log(path: Path, started: str, entries: list[dict[str, str]], summary: Mapping[str, Any], error: str | None = None) -> None:
    lines = [
        f"AutoTLE run: {started}",
        "Summary: lists={lists} satellites={satellites} added={added} updated={updated} stale={stale} same={same} skipped={skipped} errors={errors}".format(**summary),
    ]
    if error:
        lines.append(f"Run error: {error}")
    lines.append("")
    lines.append("time\tlist\tsatellite_id\tname\tsource\tstatus\tdetail")
    for entry in entries:
        lines.append("\t".join([
            entry.get("time", ""),
            entry.get("list", ""),
            entry.get("id", ""),
            entry.get("name", ""),
            entry.get("source", ""),
            entry.get("status", ""),
            entry.get("detail", ""),
        ]))
    _atomic_write(path, "\n".join(lines) + "\n")


def _delete_kind(value: str) -> tuple[str | None, str]:
    text = str(value).strip()
    if not text:
        return None, text
    if ":" in text:
        prefix, remainder = text.split(":", 1)
        prefix = prefix.strip().upper()
        remainder = remainder.strip()
        if prefix in {"NORAD", "TLE", "CATNR", "SATNUM"}:
            return "norad", remainder
        if prefix in {"INTDES", "INTL"}:
            return "intdes", remainder
    if "-" in text:
        return "intdes", text
    return "norad", text


def _delete_match_keys(state: Mapping[str, Any], value: str, catalog: Mapping[str, int]) -> set[str]:
    kind, token = _delete_kind(value)
    if kind is None or not token:
        return set()
    index = state_index(state)
    if kind == "intdes":
        compact = re.sub(r"[^A-Z0-9]", "", token.upper())
        if not compact:
            return set()
        matches: set[str] = set()
        for key, position in index.items():
            record = state["ephemeris"][position]
            object_id = re.sub(r"[^A-Z0-9]", "", str(record.get("OBJECT_ID") or "").upper())
            if object_id == compact or object_id.startswith(compact):
                matches.add(key)
        return matches

    number = parse_int(token)
    if number is None:
        return set()
    alias_matches = {key for key, alias in catalog.items() if alias == number}
    if alias_matches:
        return alias_matches
    matches = set()
    for key, position in index.items():
        record = state["ephemeris"][position]
        if parse_int(record.get("NORAD_CAT_ID")) == number:
            matches.add(key)
    return matches


def delete_state_records(options: PipelineOptions, values: Iterable[str]) -> dict[str, Any]:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    state = load_state(options.state_path)
    catalog = catalog_numbers(state)
    index = state_index(state)
    remove_keys: set[str] = set()
    details: list[dict[str, str]] = []
    requested = 0
    missing = 0

    for raw_value in values:
        requested += 1
        matches = _delete_match_keys(state, str(raw_value), catalog)
        if not matches:
            missing += 1
            details.append({
                "id": str(raw_value),
                "status": "未找到",
                "detail": "",
            })
            continue
        for key in sorted(matches, key=lambda item: index.get(item, 10**9)):
            position = index.get(key)
            if position is None:
                continue
            record = state["ephemeris"][position]
            remove_keys.add(key)
            details.append({
                "id": str(raw_value),
                "matched_id": str(record.get("NORAD_CAT_ID") or record.get("OBJECT_ID") or ""),
                "name": str(record.get("OBJECT_NAME") or ""),
                "status": "成功删除",
                "detail": "",
            })

    if remove_keys:
        state["ephemeris"] = [
            record for record in state.get("ephemeris", [])
            if (omm_identity(record) or "") not in remove_keys
        ]
        for key in remove_keys:
            for field_name in ("aliases", "sources", "status", "timestamps"):
                target = state.get(field_name)
                if isinstance(target, dict):
                    target.pop(key, None)
        ensure_aliases(state)
        save_state(options.state_path, state)

    summary = {
        "lists": 0,
        "satellites": len(state.get("ephemeris", [])),
        "added": 0,
        "updated": 0,
        "stale": 0,
        "same": 0,
        "skipped": 0,
        "errors": missing,
    }
    log_entries = [
        {
            "time": started,
            "key": "",
            "list": "delete",
            "id": item["id"],
            "name": item.get("name", ""),
            "source": "satellites.pkl",
            "status": item["status"],
            "detail": item.get("detail", ""),
        }
        for item in details
    ]
    _write_run_log(options.project_root / "logs.txt", started, log_entries, summary)
    _write_status_md(options.project_root / "satellites_state.md", state, started)
    return {
        "requested": requested,
        "deleted": len(remove_keys),
        "missing": missing,
        "remaining": len(state.get("ephemeris", [])),
        "details": details,
    }


def run_pipeline(options: PipelineOptions) -> dict[str, Any]:
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    state: dict[str, Any] | None = None
    reports: list[ListRunReport] = []
    log_entries: list[dict[str, str]] = []
    fetch_cache = RunFetchCache()
    top_error: str | None = None
    previous_statuses: dict[str, str] = {}
    status_updated = False
    try:
        state = load_state(options.state_path)
        previous_statuses = {
            key: str(value.get("current_status") or "首次记录")
            for key, value in (state.get("status") or {}).items()
        }
        list_paths = list(options.list_paths) if options.list_paths else discover_satellite_lists(options.project_root)
        if not list_paths:
            raise FileNotFoundError("no satellite list found under satellitelists/ or satelist.json")
        for list_path in list_paths:
            path = Path(list_path)
            try:
                report = _process_list(options, state, path, fetch_cache)
            except Exception as exc:
                log_entries.append({
                    "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "key": "",
                    "list": path.name,
                    "id": "-",
                    "name": "-",
                    "source": "-",
                    "status": "失败",
                    "detail": str(exc),
                })
                continue
            reports.append(report)
            log_entries.extend(report.log_entries)
        _update_status(state, previous_statuses, log_entries, started)
        status_updated = True
        ensure_aliases(state)
        if not options.dry_run:
            options.output_dir.mkdir(parents=True, exist_ok=True)
            for report in reports:
                report.outputs = _write_formats(report.config, state, report.keys, options)
            save_state(options.state_path, state)
        summary = _summary_from_reports(state, reports)
        return {"state": state, "reports": reports, "summary": summary}
    except Exception as exc:
        top_error = str(exc)
        log_entries.append({
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "key": "",
            "list": "-",
            "id": "-",
            "name": "-",
            "source": "-",
            "status": "失败",
            "detail": top_error,
        })
        raise
    finally:
        if state is not None and not status_updated:
            try:
                _update_status(state, previous_statuses, log_entries, started)
            except Exception:
                pass
        summary = _summary_from_reports(state, reports)
        try:
            _write_run_log(options.project_root / "logs.txt", started, log_entries, summary, top_error)
        except Exception:
            pass
        status_path = options.project_root / "satellites_state.md"
        try:
            if state is None:
                _atomic_write(status_path, f"# AutoTLE Satellite Cache Status\n\n- generated: {started}\n")
            else:
                _write_status_md(status_path, state, started)
        except Exception:
            pass
