"""Feasible start times for shiftable blocks (hour-of-day windows, max shift, horizon)."""

from __future__ import annotations

import logging

from app.models import AllowedWindow, ApplianceBlock

logger = logging.getLogger(__name__)


def slots_per_day_from_granularity(granularity_sec: int) -> int:
    """Calendar slots per day (e.g. granularity 3600 s -> 24 hourly slots)."""
    if granularity_sec <= 0:
        return 24
    return max(1, 86400 // granularity_sec)


def _same_day_bounds(
    original_start: int, horizon: int, slots_per_day: int
) -> tuple[int, int]:
    """Half-open [day_start, day_end) for the calendar day containing original_start."""
    day_o = original_start // slots_per_day
    day_start = day_o * slots_per_day
    day_end = min(day_start + slots_per_day, horizon)
    return day_start, day_end


def _movement_within_same_day(
    s: int,
    duration: int,
    original_start: int,
    horizon: int,
    slots_per_day: int,
) -> bool:
    """True if the whole block [s, s+duration) lies in the same day as original_start."""
    day_start, day_end = _same_day_bounds(original_start, horizon, slots_per_day)
    return day_start <= s and s + duration <= day_end


def _hour_of_slot(slot_index: int) -> int:
    return slot_index % 24


def _hour_in_window(h: int, w: AllowedWindow) -> bool:
    """Half-open [startHour, endHour) in 24h; supports wrap when start > end."""
    s, e = w.startHour, w.endHour
    if s < e:
        return s <= h < e
    if s > e:
        return h >= s or h < e
    return False


def _block_slots_in_allowed_windows(
    start_s: int, duration: int, windows: list[AllowedWindow]
) -> bool:
    for k in range(duration):
        h = _hour_of_slot(start_s + k)
        if not any(_hour_in_window(h, w) for w in windows):
            return False
    return True


def _max_shift_ok(start_s: int, original: int, max_shift: int | None) -> bool:
    if max_shift is None:
        return True
    return abs(start_s - original) <= max_shift


def feasible_starts(
    block: ApplianceBlock,
    horizon: int,
    *,
    slots_per_day: int = 24,
) -> list[int]:
    """
    Integer start indices s such that the block fits in [0, horizon), stays within the
    same calendar day as the original start (not across the bill cycle), and optional
    constraints (maxShiftHours, allowedWindows on hour-of-day) hold.
    """
    d = block.duration
    original = block.start_t
    cons = block.constraints
    max_shift = cons.maxShiftHours if cons else None
    windows = cons.allowedWindows if cons else None

    day_start, day_end = _same_day_bounds(original, horizon, slots_per_day)
    logger.debug(
        "feasible_starts blockId=%s original=%s duration=%s horizon=%s "
        "slots_per_day=%s same_day_window=[%s,%s)",
        block.blockId,
        original,
        d,
        horizon,
        slots_per_day,
        day_start,
        day_end,
    )
    if d > day_end - day_start:
        logger.debug(
            "feasible_starts empty: duration %s exceeds day span %s",
            d,
            day_end - day_start,
        )
        return []

    out: list[int] = []
    for s in range(0, horizon - d + 1):
        if not _movement_within_same_day(s, d, original, horizon, slots_per_day):
            continue
        if not _max_shift_ok(s, original, max_shift):
            continue
        if windows:
            if not _block_slots_in_allowed_windows(s, d, windows):
                continue
        out.append(s)
    logger.debug(
        "feasible_starts blockId=%s count=%s starts=%s",
        block.blockId,
        len(out),
        out if len(out) <= 48 else f"{out[:24]}... (+{len(out) - 24} more)",
    )
    return out
