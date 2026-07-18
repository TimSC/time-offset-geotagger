from datetime import datetime, timezone

from time_offset_geotagger.gpx import TrackPoint, interpolate, parse_gpx_time


def test_parse_gpx_time_treats_z_as_utc():
    assert parse_gpx_time("2026-07-18T12:34:56Z") == datetime(
        2026, 7, 18, 12, 34, 56, tzinfo=timezone.utc
    )


def test_interpolate_between_track_points():
    points = [
        TrackPoint(datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc), 51.0, -1.0, 100.0),
        TrackPoint(datetime(2026, 7, 18, 10, 10, tzinfo=timezone.utc), 52.0, 1.0, 200.0),
    ]

    result = interpolate(points, datetime(2026, 7, 18, 10, 5, tzinfo=timezone.utc))

    assert result is not None
    assert result.lat == 51.5
    assert result.lon == 0.0
    assert result.ele == 150.0


def test_interpolate_returns_none_outside_track():
    points = [TrackPoint(datetime(2026, 7, 18, 10, 0, tzinfo=timezone.utc), 51.0, -1.0)]

    assert interpolate(points, datetime(2026, 7, 18, 9, 59, tzinfo=timezone.utc)) is None
