from lib.vacancy import ANCHOR, parse_date

SAMPLE = "BÁCS-KISKUN 030090035 V 6034 Helvécia Kiskőrösi út 49. 2 696 2025.01.01"


def test_anchor_extracts_korzet_type_postal():
    m = ANCHOR.search(SAMPLE)
    assert m is not None
    assert m.groups() == ("030090035", "V", "6034")


def test_parse_date_valid():
    assert parse_date("2025.01.01") == "2025-01-01"
    assert parse_date(SAMPLE) == "2025-01-01"


def test_parse_date_invalid():
    assert parse_date("not a date") is None
    assert parse_date("2025.13.01") is None     # month 13 -> ValueError -> None
    assert parse_date(None) is None
