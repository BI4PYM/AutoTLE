from __future__ import annotations

import math
import re
from datetime import datetime, timedelta
from typing import Any

from .omm import parse_float, parse_int


ALPHA5_VALUES = {
    "A": 10, "B": 11, "C": 12, "D": 13, "E": 14, "F": 15, "G": 16, "H": 17,
    "J": 18, "K": 19, "L": 20, "M": 21, "N": 22, "P": 23, "Q": 24, "R": 25,
    "S": 26, "T": 27, "U": 28, "V": 29, "W": 30, "X": 31, "Y": 32, "Z": 33,
}
ALPHA5_LETTERS = {value: key for key, value in ALPHA5_VALUES.items()}


def is_tle_line(line: str, number: int | None = None) -> bool:
    if not line or len(line) < 3 or line[0] not in {"1", "2"} or line[1] != " ":
        return False
    return number is None or line[0] == str(number)


def split_tle_sets(text: str) -> list[tuple[str, str, str]]:
    lines = [line.rstrip("\r\n") for line in text.replace("\ufeff", "").splitlines()]
    sets: list[tuple[str, str, str]] = []
    index = 0
    while index + 1 < len(lines):
        line1 = lines[index]
        line2 = lines[index + 1]
        if not (is_tle_line(line1, 1) and is_tle_line(line2, 2)):
            index += 1
            continue
        name = ""
        if index > 0:
            previous = lines[index - 1]
            if previous.startswith("0 "):
                name = previous[2:]
            elif previous and not is_tle_line(previous, 1) and not is_tle_line(previous, 2):
                name = previous
        sets.append((name.strip(), line1.ljust(69), line2.ljust(69)))
        index += 2
    return sets


def parse_tle_catalog_number(value: str) -> int | None:
    text = value.strip().upper()
    if text.isdigit():
        return int(text)
    if len(text) == 5 and text[0] in ALPHA5_VALUES and text[1:].isdigit():
        return ALPHA5_VALUES[text[0]] * 10000 + int(text[1:])
    return None


def format_tle_catalog_number(value: int) -> str:
    number = int(value)
    if 0 <= number <= 99999:
        return f"{number:05d}"
    if 100000 <= number <= 339999:
        prefix, remainder = divmod(number, 10000)
        letter = ALPHA5_LETTERS.get(prefix)
        if letter:
            return f"{letter}{remainder:04d}"
    raise ValueError(f"catalog number cannot be encoded in five TLE columns: {value}")


def tle_checksum(line: str) -> int:
    total = 0
    for char in line[:68]:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
    return total % 10


def append_tle_checksum(line: str) -> str:
    core = line[:68].ljust(68)
    return core + str(tle_checksum(core))


def parse_tle_exponential(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    match = re.fullmatch(r"([+\- ]?)(\d{5})([+\-]\d+)", text)
    if not match:
        return None
    sign, digits, exponent = match.groups()
    mantissa = int(digits) / 100000.0
    if sign.strip() == "-":
        mantissa = -mantissa
    return mantissa * (10.0 ** int(exponent))


def parse_tle_implied_decimal(value: str) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None

def format_tle_implied_decimal(value: Any) -> str:
    number = parse_float(value) or 0.0
    rendered = f"{number:.8f}"
    if rendered.startswith("0."):
        return " " + rendered[1:]
    if rendered.startswith("-0."):
        return "-" + rendered[2:]
    return f"{number: .8f}"[:10].rjust(10)


def format_tle_exponential(value: Any) -> str:
    number = parse_float(value) or 0.0
    sign = "-" if number < 0 else " "
    magnitude = abs(number)
    if magnitude == 0:
        digits, exponent = 0, 0
    else:
        exponent = int(math.floor(math.log10(magnitude)))
        mantissa = magnitude / (10.0 ** exponent)
        digits = int(round(mantissa * 100000.0))
        while digits >= 100000:
            digits = int(round(digits / 10.0))
            exponent += 1
    return f"{sign}{digits:05d}{exponent:+d}".rjust(8)


def format_tle_epoch(value: Any) -> str:
    from .omm import parse_epoch_value

    dt = parse_epoch_value(value)
    if dt is None:
        raise ValueError(f"invalid OMM EPOCH: {value!r}")
    day = dt.timetuple().tm_yday
    fraction = (dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1_000_000) / 86400.0
    return f"{dt.year % 100:02d}{day + fraction:012.8f}"


def parse_tle_epoch(value: str) -> datetime | None:
    text = value.strip()
    if len(text) < 5:
        return None
    try:
        year2 = int(text[:2])
        day = float(text[2:])
    except ValueError:
        return None
    year = 1900 + year2 if year2 >= 57 else 2000 + year2
    try:
        return datetime(year, 1, 1) + timedelta(days=day - 1)
    except (OverflowError, ValueError):
        return None


def parse_intl_designator(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip().upper()
    match = re.match(r"^(\d{4})-(\d{3})([A-Z0-9]*)$", text)
    if match:
        year = int(match.group(1))
        launch = match.group(2)
        piece = match.group(3)
        return f"{year:04d}-{launch}{piece}"

    compact = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    if len(compact) >= 8 and compact[:4].isdigit():
        year = int(compact[:4])
        launch = compact[4:7]
        piece = compact[7:]
    elif len(compact) >= 5:
        year2 = int(compact[:2])
        year = 1900 + year2 if year2 >= 57 else 2000 + year2
        launch = compact[2:5]
        piece = compact[5:]
    else:
        return ""
    if not launch.isdigit():
        return ""
    return f"{year:04d}-{launch}{piece}"


def format_intl_designator(value: Any) -> str:
    if value is None:
        return " " * 8
    text = str(value).strip().upper()
    if not text:
        return " " * 8
    parsed = parse_intl_designator(text)
    if parsed:
        year, rest = parsed.split("-", 1)
        return (year[-2:] + rest).ljust(8)[:8]
    compact = re.sub(r"[^A-Z0-9]", "", text)
    return compact.ljust(8)[:8]

def parse_tle_set(name: str, line1: str, line2: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    line1 = line1.ljust(69)
    line2 = line2.ljust(69)
    catalog = parse_tle_catalog_number(line1[2:7])
    epoch = parse_tle_epoch(line1[18:32])
    if epoch is None:
        raise ValueError(f"invalid TLE epoch in line: {line1!r}")

    record: dict[str, Any] = {
        "CCSDS_OMM_VERS": "2.0",
        "CREATION_DATE": "",
        "ORIGINATOR": "",
        "OBJECT_NAME": (name or "").strip(),
        "OBJECT_ID": parse_intl_designator(line1[9:17]),
        "CENTER_NAME": "EARTH",
        "REF_FRAME": "TEME",
        "TIME_SYSTEM": "UTC",
        "MEAN_ELEMENT_THEORY": "SGP/SGP4",
        "EPOCH": epoch.isoformat(timespec="microseconds"),
        "MEAN_MOTION": parse_float(line2[52:63]),
        "ECCENTRICITY": parse_float("0." + line2[26:33].strip()) if line2[26:33].strip() else None,
        "INCLINATION": parse_float(line2[8:16]),
        "RA_OF_ASC_NODE": parse_float(line2[17:25]),
        "ARG_OF_PERICENTER": parse_float(line2[34:42]),
        "MEAN_ANOMALY": parse_float(line2[43:51]),
        "EPHEMERIS_TYPE": parse_int(line1[62:63]),
        "CLASSIFICATION_TYPE": (line1[7:8].strip() or "U"),
        "NORAD_CAT_ID": catalog,
        "ELEMENT_SET_NO": parse_int(line1[64:68]),
        "REV_AT_EPOCH": parse_int(line2[63:68]),
        "BSTAR": parse_tle_exponential(line1[53:61]),
        "MEAN_MOTION_DOT": parse_tle_implied_decimal(line1[33:43]),
        "MEAN_MOTION_DDOT": parse_tle_exponential(line1[44:52]),
    }
    if metadata:
        for key, value in metadata.items():
            if value is not None and key not in record:
                record[key] = value
    return record


def parse_tle_text(text: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name, line1, line2 in split_tle_sets(text):
        try:
            records.append(parse_tle_set(name, line1, line2))
        except ValueError:
            continue
    return records


def build_tle_lines(record: Mapping[str, Any], catalog_number: int, name: str | None = None) -> tuple[str, str, str]:
    display_name = (name if name is not None else str(record.get("OBJECT_NAME") or "")).strip()[:24]
    catalog = format_tle_catalog_number(catalog_number)
    classification = str(record.get("CLASSIFICATION_TYPE") or "U").strip().upper()[:1] or "U"
    intl = format_intl_designator(record.get("OBJECT_ID"))
    epoch = format_tle_epoch(record.get("EPOCH"))
    ndot = format_tle_implied_decimal(record.get("MEAN_MOTION_DOT"))
    nddot = format_tle_exponential(record.get("MEAN_MOTION_DDOT"))
    bstar = format_tle_exponential(record.get("BSTAR"))
    ephemeris_type = parse_float(record.get("EPHEMERIS_TYPE"))
    ephemeris_type = 0 if ephemeris_type is None else int(ephemeris_type)
    element_set = int(parse_float(record.get("ELEMENT_SET_NO")) or 999) % 10000
    line1_core = (
        f"1 {catalog}{classification} {intl} {epoch} "
        f"{ndot} {nddot} {bstar} {ephemeris_type:1d} {element_set:4d}"
    )
    line1 = append_tle_checksum(line1_core)

    inclination = parse_float(record.get("INCLINATION")) or 0.0
    raan = parse_float(record.get("RA_OF_ASC_NODE")) or 0.0
    eccentricity = parse_float(record.get("ECCENTRICITY")) or 0.0
    eccentricity_digits = max(0, min(9999999, int(eccentricity * 10_000_000)))
    argp = parse_float(record.get("ARG_OF_PERICENTER")) or 0.0
    mean_anomaly = parse_float(record.get("MEAN_ANOMALY")) or 0.0
    mean_motion = parse_float(record.get("MEAN_MOTION")) or 0.0
    revolutions = int(parse_float(record.get("REV_AT_EPOCH")) or 0) % 100000
    line2_core = (
        f"2 {catalog} {inclination:8.4f} {raan:8.4f} "
        f"{eccentricity_digits:07d} {argp:8.4f} {mean_anomaly:8.4f} "
        f"{mean_motion:11.8f}{revolutions:5d}"
    )
    line2 = append_tle_checksum(line2_core)
    return display_name, line1, line2


def omm_to_tle(record: Mapping[str, Any], catalog_number: int | None = None, name: str | None = None) -> str:
    real_catalog = parse_int(record.get("NORAD_CAT_ID"))
    if real_catalog is None:
        raise ValueError("NORAD_CAT_ID is required to generate TLE")
    selected = real_catalog if catalog_number is None else int(catalog_number)
    display_name, line1, line2 = build_tle_lines(record, selected, name)
    return f"{display_name:<24}\n{line1}\n{line2}\n"


def render_tle(
    records: Iterable[Mapping[str, Any]],
    catalog_numbers: Mapping[str, int] | None = None,
    names: Mapping[str, str] | None = None,
    include_name: bool = True,
) -> str:
    from .omm import omm_identity

    blocks: list[str] = []
    for record in records:
        key = omm_identity(record) or ""
        real_catalog = parse_int(record.get("NORAD_CAT_ID"))
        if real_catalog is None:
            continue
        catalog = (catalog_numbers or {}).get(key, real_catalog)
        display_name, line1, line2 = build_tle_lines(record, catalog, (names or {}).get(key))
        if include_name:
            blocks.append(f"{display_name:<24}\n{line1}\n{line2}")
        else:
            blocks.append(f"{line1}\n{line2}")
    return "\n".join(blocks) + ("\n" if blocks else "")
