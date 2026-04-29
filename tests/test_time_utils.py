from datetime import datetime

from src.utils import time_utils


def test_incremental_query_range_uses_last_check_with_overlap(monkeypatch):
    fixed_now = datetime(2026, 4, 30, 12, 0, tzinfo=time_utils.KST)
    monkeypatch.setattr(time_utils, "now_kst", lambda: fixed_now)

    begin, end = time_utils.get_incremental_query_range(
        "2026-04-30T10:30:00+09:00",
        buffer_hours=1,
        overlap_minutes=15,
    )

    assert begin == "202604301015"
    assert end == "202604301200"


def test_incremental_query_range_falls_back_without_last_check(monkeypatch):
    fixed_now = datetime(2026, 4, 30, 12, 0, tzinfo=time_utils.KST)
    monkeypatch.setattr(time_utils, "now_kst", lambda: fixed_now)

    begin, end = time_utils.get_incremental_query_range("", buffer_hours=1)

    assert begin == "202604301100"
    assert end == "202604301200"
