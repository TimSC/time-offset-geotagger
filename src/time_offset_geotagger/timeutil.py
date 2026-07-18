from __future__ import annotations

from datetime import datetime, timezone


def parse_actual_time(value: str) -> datetime:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        raise ValueError("Actual phone time must include a timezone or Z")
    return parsed.astimezone(timezone.utc)


def parse_actual_date_time(date_value: str, time_value: str, timezone_value: str) -> datetime:
    zone = timezone_value.strip()
    if not zone:
        raise ValueError("Timezone must be entered as Z or an offset such as +01:00")
    if zone.upper() == "Z":
        zone = "+00:00"
    return parse_actual_time(f"{date_value.strip()}T{time_value.strip()}{zone}")


def format_offset(seconds: float) -> str:
    sign = "+" if seconds >= 0 else "-"
    remaining = abs(int(round(seconds)))
    hours, remaining = divmod(remaining, 3600)
    minutes, seconds = divmod(remaining, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"
