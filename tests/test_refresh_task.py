from datetime import datetime

import pytest

from src.refresh_task import RefreshTask


@pytest.mark.parametrize(
    "current,interval,expected",
    [
        (datetime(2026, 8, 10, 12, 15, 0), 3600, 2700),
        (datetime(2026, 8, 10, 12, 59, 30), 3600, 30),
        (datetime(2026, 8, 10, 12, 0, 50), 3600, 3550),
        (datetime(2026, 8, 10, 12, 2, 30), 300, 150),
        (datetime(2026, 8, 10, 12, 0, 0), 3600, 3600),
    ],
)
def test_seconds_until_next_interval(current, interval, expected):
    assert RefreshTask._seconds_until_next_interval(current, interval) == expected


def test_seconds_until_next_interval_handles_nonpositive_interval():
    current = datetime(2026, 8, 10, 12, 0, 0, 500000)

    assert RefreshTask._seconds_until_next_interval(current, 0) == 0.5
