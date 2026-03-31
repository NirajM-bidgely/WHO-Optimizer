import pytest

from app.feasible import feasible_starts
from app.models import AllowedWindow, ApplianceBlock, BlockConstraints


def test_feasible_max_shift_two_from_17():
    # Window [12,20) so hours 17–19 (3-slot block from 17) fit; [12,18) would exclude hour 19.
    b = ApplianceBlock(
        blockId=1,
        start_t=17,
        duration=3,
        consumption=[1.0, 1.0, 1.0],
        constraints=BlockConstraints(
            maxShiftHours=2,
            allowedWindows=[AllowedWindow(startHour=12, endHour=20)],
        ),
    )
    S = feasible_starts(b, 744)
    assert 17 in S
    assert 15 in S
    assert 14 not in S  # |14-17| = 3 > 2


def test_feasible_max_shift_three_allows_14():
    b = ApplianceBlock(
        blockId=1,
        start_t=17,
        duration=3,
        consumption=[1.0, 1.0, 1.0],
        constraints=BlockConstraints(
            maxShiftHours=3,
            allowedWindows=[AllowedWindow(startHour=12, endHour=20)],
        ),
    )
    assert 14 in feasible_starts(b, 744)


def test_feasible_same_day_excludes_other_calendar_days():
    b = ApplianceBlock(
        blockId=1,
        start_t=30,
        duration=2,
        consumption=[1.0, 1.0],
        constraints=None,
    )
    S = feasible_starts(b, 48, slots_per_day=24)
    assert 30 in S
    assert 24 in S
    assert 0 not in S
    assert 23 not in S


def test_empty_feasible_when_window_too_tight():
    b = ApplianceBlock(
        blockId=1,
        start_t=17,
        duration=3,
        consumption=[1.0, 1.0, 1.0],
        constraints=BlockConstraints(
            maxShiftHours=0,
            allowedWindows=[AllowedWindow(startHour=12, endHour=14)],
        ),
    )
    assert feasible_starts(b, 744) == []
