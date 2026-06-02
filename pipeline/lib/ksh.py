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
