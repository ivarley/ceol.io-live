"""The window rule behind /sessions/<festival> (spec 056 "Reaching the right
year"), and the picker's order. Pure: years are dicts, `now` is passed in."""

import datetime as dt

from festivals import (
    FESTIVAL_WINDOW_AFTER_DAYS,
    FESTIVAL_WINDOW_BEFORE_DAYS,
    picker_order,
    window_pick,
)

D = dt.date
UTC = dt.timezone.utc


def year(y, start, end=None, tz="America/Chicago"):
    return {
        "year": y,
        "path": f"fest/{y}",
        "initiation_date": start,
        "termination_date": end,
        "timezone": tz,
    }


def at(date, hour=12):
    return dt.datetime(date.year, date.month, date.day, hour, tzinfo=UTC)


Y2025 = year(2025, D(2025, 10, 23), D(2025, 10, 26))
Y2026 = year(2026, D(2026, 10, 22), D(2026, 10, 25))


def test_one_year_wins_whatever_the_date():
    assert window_pick([Y2025], at(D(2030, 1, 1)))["year"] == 2025


def test_no_years():
    assert window_pick([], at(D(2026, 1, 1))) is None


def test_outside_every_window_is_the_picker():
    assert window_pick([Y2025, Y2026], at(D(2026, 6, 1))) is None


def test_opens_a_week_before():
    first = D(2026, 10, 22) - dt.timedelta(days=FESTIVAL_WINDOW_BEFORE_DAYS)
    assert window_pick([Y2025, Y2026], at(first))["year"] == 2026
    assert window_pick([Y2025, Y2026], at(first - dt.timedelta(days=1))) is None


def test_closes_a_month_after_the_end():
    last = D(2025, 10, 26) + dt.timedelta(days=FESTIVAL_WINDOW_AFTER_DAYS)
    assert window_pick([Y2025, Y2026], at(last))["year"] == 2025
    assert window_pick([Y2025, Y2026], at(last + dt.timedelta(days=1))) is None


def test_today_is_the_festivals_today_not_utcs():
    # 03:00 UTC on Oct 15 is still Oct 14 in Chicago: one day short of the window.
    opens = D(2026, 10, 15)
    early_utc = dt.datetime(2026, 10, 15, 3, tzinfo=UTC)
    assert window_pick([Y2025, Y2026], early_utc) is None
    assert window_pick([Y2025, Y2026], at(opens, hour=6))["year"] == 2026


def test_a_null_end_counts_from_the_first_day():
    y = year(2026, D(2026, 3, 1))
    other = year(2024, D(2024, 3, 1), D(2024, 3, 3))
    assert window_pick([other, y], at(D(2026, 3, 31)))["year"] == 2026
    assert window_pick([other, y], at(D(2026, 4, 1))) is None


def test_two_in_the_window_the_nearer_first_day_wins():
    spring = year(2026, D(2026, 5, 1), D(2026, 5, 3))
    early_summer = year(
        2027, D(2026, 5, 20), D(2026, 5, 22)
    )  # held twice in five weeks
    assert window_pick([spring, early_summer], at(D(2026, 5, 15)))["year"] == 2027
    assert window_pick([spring, early_summer], at(D(2026, 5, 5)))["year"] == 2026


def test_picker_order_upcoming_first_then_newest_first():
    y2024 = year(2024, D(2024, 10, 24), D(2024, 10, 27))
    order = picker_order([y2024, Y2025, Y2026], at(D(2026, 6, 1)))
    assert [y["year"] for y in order] == [2026, 2025, 2024]


def test_picker_order_with_two_upcoming_nearest_leads():
    y2027 = year(2027, D(2027, 10, 21), D(2027, 10, 24))
    order = picker_order([Y2025, y2027, Y2026], at(D(2026, 6, 1)))
    assert [y["year"] for y in order] == [2026, 2027, 2025]
