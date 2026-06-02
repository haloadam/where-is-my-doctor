from lib.ksh import is_valid, parse_served_cell, zfill5


def test_zfill5_preserves_leading_zeros():
    assert zfill5("5403") == "05403"
    assert zfill5("403") == "00403"
    assert zfill5("12548") == "12548"
    assert zfill5(12548) == "12548"          # ints coerced to strings
    assert zfill5("  12548 ") == "12548"     # whitespace trimmed


def test_zfill5_rejects_bad_input():
    assert zfill5("123456") is None          # >5 digits
    assert zfill5("abc") is None
    assert zfill5("") is None
    assert zfill5(None) is None


def test_is_valid():
    assert is_valid("05403")
    assert not is_valid("5403")              # 4 digits
    assert not is_valid("123456")
    assert not is_valid(None)


def test_parse_served_cell_multi():
    pairs, fails = parse_served_cell("12548 Abaliget,14517 Kovácsszénája,31431 Husztót")
    assert fails == 0
    assert pairs == [("12548", "Abaliget"), ("14517", "Kovácsszénája"), ("31431", "Husztót")]


def test_parse_served_cell_leading_zero_kept_as_string():
    pairs, fails = parse_served_cell("05403 Babarc")
    assert pairs == [("05403", "Babarc")]
    assert isinstance(pairs[0][0], str)


def test_parse_served_cell_blank_and_failures():
    assert parse_served_cell("") == ([], 0)
    assert parse_served_cell(None) == ([], 0)
    pairs, fails = parse_served_cell("12548 Abaliget, , no-code-here")
    assert pairs == [("12548", "Abaliget")]
    assert fails == 1                        # "no-code-here" doesn't match, empty entry skipped
