"""Hungarian settlement-name normalisation for fuzzy joins (OSM <-> KSH)."""
from __future__ import annotations

import re

from unidecode import unidecode

# Common OSM/KSH formatting differences to neutralise before comparison.
_PAREN = re.compile(r"\(.*?\)")
_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^a-z0-9 ]")


def normalize(name: str | None) -> str:
    """Lowercase, strip accents, drop parentheticals/punctuation, collapse spaces.

    "Budapest I. kerület" -> "budapest i kerulet"; "Hódmezővásárhely" -> "hodmezovasarhely".
    Accents are only stripped for *matching*; the canonical display name keeps them.
    """
    if not name:
        return ""
    s = unidecode(str(name)).lower()
    s = _PAREN.sub(" ", s)
    s = s.replace(".", " ")
    s = _NONWORD.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s
