"""Vacancy-PDF text patterns — pure, importable, unit-tested (tests/test_vacancy.py).

Each vacancy row is anchored by a 9-digit körzet code + type (V/F/G) + 4-digit postal code,
and carries a YYYY.MM.DD start date. The settlement-name column is unreliable, so vacancies are
joined to settlements via the körzet code, not the name."""
from __future__ import annotations

import re
from datetime import date

ANCHOR = re.compile(r"(\d{9})\s+([VFG])\s+(\d{4})")
DATE = re.compile(r"(20\d{2})\.\s?(\d{2})\.\s?(\d{2})")


def parse_date(s: str | None) -> str | None:
    """First YYYY.MM.DD in `s` as an ISO date string, or None."""
    m = DATE.search(s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None
