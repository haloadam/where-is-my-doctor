from lib.names import normalize


def test_strips_accents_and_case():
    assert normalize("Hódmezővásárhely") == "hodmezovasarhely"
    assert normalize("Pécs") == "pecs"
    assert normalize("Győr") == "gyor"


def test_drops_parentheticals_and_punctuation():
    assert normalize("Budapest I. kerület") == "budapest i kerulet"
    assert normalize("Tököl (külterület)") == "tokol"


def test_empty_and_none():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_collapses_whitespace():
    assert normalize("  Nagy   Bajom ") == "nagy bajom"
