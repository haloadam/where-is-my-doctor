"""KSH settlement-code helpers. Codes are 5-digit zero-padded strings (törzsszám);
782 distinct codes have a leading zero, so they MUST be strings, never ints."""
from __future__ import annotations

import re

_DIGITS = re.compile(r"\d+")
CODE_RE = re.compile(r"^\d{5}$")
# A col-K entry is "<5-digit code> <settlement name>".
K_PAIR_RE = re.compile(r"^\s*(\d{5})\s+(.+?)\s*$")


def zfill5(code) -> str | None:
    """Coerce any KSH-code-ish value to a 5-digit zero-padded string, or None."""
    if code is None:
        return None
    s = str(code).strip()
    if not s:
        return None
    m = _DIGITS.search(s)
    if not m:
        return None
    digits = m.group(0)
    if len(digits) > 5:
        return None
    return digits.zfill(5)


def is_valid(code: str | None) -> bool:
    return bool(code) and bool(CODE_RE.match(code))


def parse_served_cell(value) -> tuple[list[tuple[str, str]], int]:
    """Parse a NEAK 'Ellátandó települések KSH kódjai' cell into (pairs, n_failures).

    "12548 Abaliget,14517 Kovácsszénája" -> ([("12548","Abaliget"),("14517","Kovácsszénája")], 0).
    Each comma-separated entry must be '<5-digit KSH code> <name>'; entries that don't match are
    counted as failures (guarded by the A-KPARSE assertion)."""
    pairs: list[tuple[str, str]] = []
    failures = 0
    for part in str(value or "").split(","):
        part = part.strip()
        if not part:
            continue
        m = K_PAIR_RE.match(part)
        if m:
            pairs.append((zfill5(m.group(1)), m.group(2).strip()))
        else:
            failures += 1
    return pairs, failures
