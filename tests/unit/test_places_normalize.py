"""places.py normalization (spec 055 "Adding a session", step 1): the pure part of
the place matcher. The slug must equal the client's generatePath clean step, or a
town created from the city text would not have the slug the sheet put in the path."""

import pytest

from places import normalize_area, normalize_country, slugify


@pytest.mark.parametrize(
    "text, slug",
    [
        ("Austin", "austin"),
        ("San Francisco", "san-francisco"),
        ("  East   Durham ", "east-durham"),
        ("O'Flaherty's Irish Music Retreat", "oflahertys-irish-music-retreat"),
        ("St. Louis", "st-louis"),
        ("Zürich", "zrich"),
        ("--a--b--", "a-b"),
        ("!!!", ""),
        (None, ""),
    ],
)
def test_slugify_matches_generate_path(text, slug):
    assert slugify(text) == slug


@pytest.mark.parametrize(
    "raw, country",
    [
        ("USA", "United States"),
        ("U.S.A.", "United States"),
        ("us", "United States"),
        ("United States", "United States"),
        ("UK", "United Kingdom"),
        ("Éire", "Ireland"),
        ("ireland", "Ireland"),
        ("Greece", "Greece"),
        ("  ", None),
        (None, None),
    ],
)
def test_normalize_country(raw, country):
    assert normalize_country(raw) == country


@pytest.mark.parametrize(
    "area, country, expected",
    [
        ("TX", "USA", "Texas"),
        ("tx", "United States", "Texas"),
        ("texas", "US", "Texas"),
        ("Texas", "USA", "Texas"),
        ("D.C.", "USA", "District of Columbia"),
        ("Somewhere", "USA", "Somewhere"),  # not a state: kept as entered
        ("Clare", "Ireland", "Clare"),
        ("TX", "Ireland", "TX"),  # only the US has a vocabulary
        ("", "USA", None),
    ],
)
def test_normalize_area(area, country, expected):
    assert normalize_area(area, country) == expected
