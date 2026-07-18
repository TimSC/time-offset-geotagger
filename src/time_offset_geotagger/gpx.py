from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree


@dataclass(frozen=True)
class TrackPoint:
    time: datetime
    lat: float
    lon: float
    ele: float | None = None


def parse_gpx(path: Path) -> list[TrackPoint]:
    root = ElementTree.parse(path).getroot()
    points: list[TrackPoint] = []

    for trkpt in root.iter():
        if _local_name(trkpt.tag) != "trkpt":
            continue

        lat = trkpt.attrib.get("lat")
        lon = trkpt.attrib.get("lon")
        if lat is None or lon is None:
            continue

        time_text: str | None = None
        ele_text: str | None = None
        for child in trkpt:
            name = _local_name(child.tag)
            if name == "time":
                time_text = child.text
            elif name == "ele":
                ele_text = child.text

        if not time_text:
            continue

        points.append(
            TrackPoint(
                time=parse_gpx_time(time_text),
                lat=float(lat),
                lon=float(lon),
                ele=float(ele_text) if ele_text else None,
            )
        )

    points.sort(key=lambda point: point.time)
    return points


def parse_gpx_time(value: str) -> datetime:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def interpolate(points: Iterable[TrackPoint], when: datetime) -> TrackPoint | None:
    ordered = sorted(points, key=lambda point: point.time)
    if when.tzinfo is None:
        raise ValueError("Interpolation time must include timezone information")
    when = when.astimezone(timezone.utc)

    if not ordered or when < ordered[0].time or when > ordered[-1].time:
        return None

    for index, point in enumerate(ordered):
        if point.time == when:
            return point
        if point.time > when:
            before = ordered[index - 1]
            after = point
            total = (after.time - before.time).total_seconds()
            ratio = 0.0 if total == 0 else (when - before.time).total_seconds() / total
            ele = None
            if before.ele is not None and after.ele is not None:
                ele = before.ele + ((after.ele - before.ele) * ratio)
            return TrackPoint(
                time=when,
                lat=before.lat + ((after.lat - before.lat) * ratio),
                lon=before.lon + ((after.lon - before.lon) * ratio),
                ele=ele,
            )

    return ordered[-1]


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
