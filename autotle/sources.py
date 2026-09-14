from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import ProxyHandler, Request, build_opener

from .config import SatelliteSpec
from .omm import OMMParseError, omm_epoch, omm_identity, parse_omm_text
from .tle import parse_tle_set, parse_tle_text

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
#USER_AGENT = "AutoTLE/2.0 (+https://github.com/BI4PYM/AutoTLE)"
CELESTRAK_ENDPOINT = "https://celestrak.org/NORAD/elements/gp.php"
SATNOGS_ENDPOINT = "https://db.satnogs.org/api/tle/"


@dataclass
class FetchResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    url: str = ""
    format: str = ""
    error: str | None = None


def _body_is_error(body: str) -> bool:
    text = body.strip().lower()
    if not text:
        return True
    return text in {"no gp data found", "not found", "error"} or text.startswith("<html")


def http_get(
    url: str,
    timeout: float = 20.0,
    retries: int = 2,
    proxy: str | None = None,
) -> tuple[int | None, str, str, str | None]:
    handlers = []
    if proxy:
        handlers.append(ProxyHandler({"http": proxy, "https": proxy}))
    opener = build_opener(*handlers)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    last_error: str | None = None

    for attempt in range(max(1, retries + 1)):
        try:
            with opener.open(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
                return response.status, body, response.headers.get("Content-Type", ""), None
        except HTTPError as exc:
            raw = exc.read()
            body = raw.decode("utf-8", errors="replace")
            last_error = f"HTTP {exc.code}"
            if exc.code < 500:
                return exc.code, body, exc.headers.get("Content-Type", ""), last_error
        except (URLError, TimeoutError, OSError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        if attempt < retries:
            time.sleep(0.75 * (attempt + 1))
    return None, "", "", last_error


def fetch_celestrak(
    spec: SatelliteSpec,
    formats: Iterable[str],
    timeout: float,
    retries: int,
    proxy: str | None,
) -> FetchResult:
    if spec.query not in {"CATNR", "NAME", "INTDES", "GROUP", "SPECIAL"}:
        return FetchResult(source="celestrak", error=f"unsupported CelesTrak query {spec.query}")
    errors: list[str] = []
    for source_format in formats:
        query = urlencode({spec.query: spec.id, "FORMAT": source_format})
        url = f"{CELESTRAK_ENDPOINT}?{query}"
        status, body, _content_type, error = http_get(url, timeout, retries, proxy)
        if status != 200 or _body_is_error(body):
            errors.append(f"{source_format}: {error or status or 'empty'}")
            continue
        try:
            records = parse_omm_text(body, source_format)
        except (OMMParseError, ValueError) as exc:
            errors.append(f"{source_format}: {exc}")
            continue
        if records:
            return FetchResult(records, "celestrak", url, source_format)
        errors.append(f"{source_format}: no records")
    return FetchResult(source="celestrak", error="; ".join(errors) or "no data")

def _satnogs_param(spec: SatelliteSpec) -> tuple[str, str] | None:
    if spec.query in {"SATID", "SAT_ID"}:
        return "sat_id", spec.id
    if spec.query == "CATNR" or spec.id.isdigit():
        return "norad_cat_id", spec.id
    return None


def _parse_satnogs_json(body: str, url: str) -> FetchResult:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return FetchResult(source="satnogs", url=url, format="json", error=f"invalid JSON: {exc}")
    items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        line1 = str(item.get("tle1") or "")
        line2 = str(item.get("tle2") or "")
        if not line1 or not line2:
            continue
        name = str(item.get("tle0") or "")
        if name.startswith("0 "):
            name = name[2:]
        try:
            record = parse_tle_set(name, line1, line2, {
                "_SOURCE": item.get("tle_source"),
                "_SOURCE_UPDATED": item.get("updated"),
                "_SAT_ID": item.get("sat_id"),
            })
        except ValueError:
            continue
        if record.get("NORAD_CAT_ID") is None and item.get("norad_cat_id") is not None:
            record["NORAD_CAT_ID"] = item.get("norad_cat_id")
        records.append(record)
    if records:
        return FetchResult(records, "satnogs", url, "3le-json")
    return FetchResult(source="satnogs", url=url, format="json", error="no TLE records")


def fetch_satnogs(spec: SatelliteSpec, timeout: float, retries: int, proxy: str | None) -> FetchResult:
    param = _satnogs_param(spec)
    if param is None:
        return FetchResult(source="satnogs", error="SatNOGS needs norad_cat_id or sat_id")
    param_name, param_value = param
    errors: list[str] = []
    for source_format in ("json", "3le"):
        url = f"{SATNOGS_ENDPOINT}?{urlencode({'format': source_format, param_name: param_value})}"
        status, body, _content_type, error = http_get(url, timeout, retries, proxy)
        if status != 200 or _body_is_error(body):
            errors.append(f"{source_format}: {error or status or 'empty'}")
            continue
        if source_format == "json":
            result = _parse_satnogs_json(body, url)
            if result.records:
                return result
            errors.append(f"json: {result.error}")
            continue
        try:
            records = parse_tle_text(body)
        except ValueError as exc:
            errors.append(f"3le: {exc}")
            continue
        if records:
            return FetchResult(records, "satnogs", url, "3le")
        errors.append("3le: no records")
    return FetchResult(source="satnogs", error="; ".join(errors) or "no data")


def _matches_spec(record: Mapping[str, Any], spec: SatelliteSpec) -> bool:
    if spec.query == "CATNR":
        try:
            wanted = int(spec.id)
        except ValueError:
            return False
        return int(record.get("NORAD_CAT_ID") or -1) == wanted
    if spec.query == "INTDES":
        wanted = spec.id.strip().upper()
        object_id = str(record.get("OBJECT_ID") or "").strip().upper()
        return bool(wanted and object_id.startswith(wanted))
    if spec.query == "NAME":
        wanted = spec.id.strip().upper()
        actual = str(record.get("OBJECT_NAME") or "").strip().upper()
        return bool(wanted and (wanted == actual or wanted in actual or actual in wanted))
    return False


def fetch_local(spec: SatelliteSpec, paths: Iterable[str | Path], source: str = "local") -> FetchResult:
    candidates: dict[str, tuple[dict[str, Any], str, str]] = {}
    order: list[str] = []
    parse_errors: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            if path.suffix.lower() == ".json":
                parsed = parse_omm_text(text, "JSON")
                file_format = "JSON"
            else:
                parsed = parse_tle_text(text)
                file_format = "TLE"
        except (OMMParseError, ValueError) as exc:
            parse_errors.append(f"{path.name}: {exc}")
            continue
        for record in parsed:
            if not _matches_spec(record, spec):
                continue
            key = omm_identity(record) or str(record.get("OBJECT_ID") or record.get("OBJECT_NAME") or "")
            if not key:
                continue
            if key not in candidates:
                candidates[key] = (record, file_format, str(path))
                order.append(key)
                continue
            old_record = candidates[key][0]
            new_epoch = omm_epoch(record)
            old_epoch = omm_epoch(old_record)
            if new_epoch is not None and (old_epoch is None or new_epoch > old_epoch):
                candidates[key] = (record, file_format, str(path))
    if candidates:
        records = [candidates[key][0] for key in order]
        used_formats = sorted({candidates[key][1] for key in order})
        used_paths = list(dict.fromkeys(candidates[key][2] for key in order))
        return FetchResult(records, source, ";".join(used_paths), "+".join(used_formats))
    error = "no matching local ephemeris"
    if parse_errors:
        error += ": " + "; ".join(parse_errors)
    return FetchResult(source=source, error=error)

def fetch_for_spec(
    spec: SatelliteSpec,
    sources: Iterable[str],
    celestrak_formats: Iterable[str],
    timeout: float,
    retries: int,
    proxy: str | None,
    local_paths: Iterable[str | Path],
) -> FetchResult:
    errors: list[str] = []
    paths = list(local_paths)
    for source in sources:
        if source == "celestrak":
            result = fetch_celestrak(spec, celestrak_formats, timeout, retries, proxy)
        elif source == "satnogs":
            result = fetch_satnogs(spec, timeout, retries, proxy)
        elif source == "localtle":
            result = fetch_local(spec, paths[:1], "localtle")
        elif source == "localjson":
            result = fetch_local(spec, paths[1:2], "localjson")
        elif source == "local":
            result = fetch_local(spec, paths, "local")
        else:
            continue
        if result.records:
            return result
        if result.error:
            errors.append(f"{source}: {result.error}")
    return FetchResult(source=",".join(sources), error="; ".join(errors) or "no source succeeded")
