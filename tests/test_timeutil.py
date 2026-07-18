from datetime import datetime, timezone

import pytest

from time_offset_geotagger.timeutil import format_offset, parse_actual_date_time, parse_actual_time


def test_parse_actual_time_requires_timezone():
    with pytest.raises(ValueError):
        parse_actual_time("2026-07-18 14:03:22")


def test_parse_actual_time_accepts_z():
    assert parse_actual_time("2026-07-18T13:03:22Z") == datetime(
        2026, 7, 18, 13, 3, 22, tzinfo=timezone.utc
    )


def test_parse_actual_date_time_joins_fields():
    assert parse_actual_date_time("2026-07-18", "14:03:22", "+01:00") == datetime(
        2026, 7, 18, 13, 3, 22, tzinfo=timezone.utc
    )


def test_format_offset():
    assert format_offset(3723) == "+01:02:03"
    assert format_offset(-62) == "-00:01:02"
