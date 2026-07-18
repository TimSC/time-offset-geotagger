from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image
import piexif

from .gpx import TrackPoint

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class Photo:
    path: Path
    taken_at: datetime


def discover_photos(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def read_taken_at(path: Path) -> datetime | None:
    try:
        with Image.open(path) as image:
            exif = image.getexif()
    except Exception:
        return None

    for tag in (36867, 36868, 306):
        raw = exif.get(tag)
        if not raw:
            continue
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        try:
            return datetime.strptime(str(raw), "%Y:%m:%d %H:%M:%S")
        except ValueError:
            continue
    return None


def load_photo(path: Path) -> Photo | None:
    taken_at = read_taken_at(path)
    if taken_at is None:
        return None
    return Photo(path=path, taken_at=taken_at)


def write_gps_tags(path: Path, point: TrackPoint) -> None:
    exif_dict = piexif.load(str(path))
    gps = dict(exif_dict.get("GPS") or {})

    lat_ref, lat_value = _coordinate_to_exif(point.lat, positive_ref="N", negative_ref="S")
    lon_ref, lon_value = _coordinate_to_exif(point.lon, positive_ref="E", negative_ref="W")
    gps[piexif.GPSIFD.GPSLatitudeRef] = lat_ref
    gps[piexif.GPSIFD.GPSLatitude] = lat_value
    gps[piexif.GPSIFD.GPSLongitudeRef] = lon_ref
    gps[piexif.GPSIFD.GPSLongitude] = lon_value

    timestamp = point.time.astimezone(timezone.utc)
    gps[piexif.GPSIFD.GPSDateStamp] = timestamp.strftime("%Y:%m:%d")
    gps[piexif.GPSIFD.GPSTimeStamp] = (
        (timestamp.hour, 1),
        (timestamp.minute, 1),
        (timestamp.second, 1),
    )

    if point.ele is not None:
        gps[piexif.GPSIFD.GPSAltitudeRef] = 0 if point.ele >= 0 else 1
        gps[piexif.GPSIFD.GPSAltitude] = _rational(abs(point.ele), precision=100)

    exif_dict["GPS"] = gps
    piexif.insert(piexif.dump(exif_dict), str(path))


def _coordinate_to_exif(value: float, positive_ref: str, negative_ref: str) -> tuple[str, tuple]:
    ref = positive_ref if value >= 0 else negative_ref
    absolute = abs(value)
    degrees = int(absolute)
    minutes_float = (absolute - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    return ref, ((degrees, 1), (minutes, 1), _rational(seconds, precision=1_000_000))


def _rational(value: float, precision: int) -> tuple[int, int]:
    return round(value * precision), precision
