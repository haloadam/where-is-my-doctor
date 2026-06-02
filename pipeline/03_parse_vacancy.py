#!/usr/bin/env python
"""Step 3 — parse the NEAK vacant-practices PDF + the OKFŐ persistence HTML table.

Vacancies are keyed by the 9-digit körzet code (identical format to the active
HSZ kód → 100% join). The settlement-name column in the PDF is unreliable, so
vacancy→settlement is resolved later (06) via körzet → active membership.

Two independent extractions cross-check each other (A-VAC-XCHECK): a line-by-line
structured parse (primary) vs a raw full-text anchor-regex count. A silent parser
regression that changes the row count trips CI."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import pdfplumber

from lib.assertions import Assertions, within
from lib.config import EXPECT, RAW_FILES
from lib.io import read_parquet, write_parquet
from lib.names import normalize
from lib.vacancy import ANCHOR, DATE, parse_date


def parse_pdf(path):
    with pdfplumber.open(path) as pdf:
        full = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    # Primary: structured line-by-line.
    rows = []
    county = None
    for line in full.splitlines():
        cm = re.match(r"^([A-ZÁÉÍÓÖŐÚÜŰ][A-ZÁÉÍÓÖŐÚÜŰ\- ]+?)\s+\d{9}\s+[VFG]\s+\d{4}", line)
        if cm:
            county = cm.group(1).strip()
        a = ANCHOR.search(line)
        if not a:
            continue
        dates = DATE.findall(line)
        vstart = parse_date(".".join(dates[-1])) if dates else None
        rows.append({"hsz_kod": a.group(1), "type": a.group(2), "postal": a.group(3),
                     "county": county, "vacancy_start": vstart})
    primary = pd.DataFrame(rows)
    xcheck = len(ANCHOR.findall(full))  # independent count
    return primary, xcheck


def parse_okfo(path):
    """Return DataFrame keyed by (county_norm, type, postal) with persistent_start.
    Raises on a read failure so the caller can surface it (A-OKFO-PARSE), rather than
    silently producing an all-False persistence flag."""
    tables = pd.read_html(path)
    best = max(tables, key=len)
    best.columns = [str(c) for c in best.columns]
    txt = best.astype(str)
    # Heuristically locate columns: a V/F/G type col, a postal (4-digit) col, two dates.
    recs = []
    for _, row in txt.iterrows():
        joined = " ".join(row.tolist())
        tm = re.search(r"\b([VFG])\b", joined)
        pm = re.search(r"\b(\d{4})\b", joined)
        dts = DATE.findall(joined)
        county = next((v for v in row.tolist() if re.match(r"^[A-ZÁÉÍÓÖŐÚÜŰ\- ]{4,}$", v)), None)
        if pm:
            recs.append({"county_norm": normalize(county), "type": tm.group(1) if tm else None,
                         "postal": pm.group(1),
                         "persistent_start": parse_date(".".join(dts[-1])) if dts else None})
    return pd.DataFrame(recs)


def main():
    a = Assertions("03_parse_vacancy")
    vac, xcheck = parse_pdf(RAW_FILES["vacancy"])
    n = len(vac)
    a.check("A-VAC-ROWS", within(n, *EXPECT["VACANCY_ROWS"]), f"{n} vacancy rows (expect ~1021)")
    a.check("A-VAC-XCHECK", within(xcheck, n, EXPECT["VAC_XCHECK_TOL"]),
            f"line-parse {n} vs anchor-regex {xcheck}")
    tcounts = vac["type"].value_counts().to_dict()
    types_ok = all(within(tcounts.get(t, 0), exp, EXPECT["VAC_TYPE_TOL"])
                   for t, exp in EXPECT["VAC_TYPES"].items())
    a.check("A-VAC-TYPES", types_ok, f"{tcounts} vs {EXPECT['VAC_TYPES']}")

    # Join coverage against active practices.
    active_hsz = set(read_parquet("practices")["hsz_kod"])
    join_frac = vac["hsz_kod"].isin(active_hsz).mean()
    a.check("A-VAC-JOIN", join_frac >= EXPECT["VAC_JOIN_MIN"],
            f"{join_frac*100:.1f}% vacancy körzets present in active list")

    # Persistence flag from OKFŐ (surface a parse failure instead of silently losing the flag).
    try:
        okfo = parse_okfo(RAW_FILES["okfo"])
    except Exception as e:  # noqa: BLE001 — degrade visibly, don't crash the whole build
        okfo = pd.DataFrame(columns=["county_norm", "type", "postal", "persistent_start"])
        a.warn("A-OKFO-PARSE", False, f"OKFŐ HTML parse failed: {e}")
    vac["county_norm"] = vac["county"].map(normalize)
    if len(okfo):
        key = ["county_norm", "type", "postal"]
        okfo_keys = okfo.dropna(subset=["postal"]).drop_duplicates(key)
        merged = vac.merge(okfo_keys[key + ["persistent_start"]], on=key, how="left")
        merged["is_persistent"] = merged["persistent_start"].notna()
        okfo_frac = merged["is_persistent"].mean()
    else:
        merged = vac.assign(persistent_start=None, is_persistent=False)
        okfo_frac = 0.0
    a.warn("A-OKFO-JOIN", okfo_frac >= EXPECT["OKFO_JOIN_MIN"],
           f"{okfo_frac*100:.1f}% vacancies flagged persistent via OKFŐ")

    out = merged.drop_duplicates(subset=["hsz_kod"]).reset_index(drop=True)
    a.stat("vacant_rows", int(len(out)))
    a.stat("persistent_rows", int(out["is_persistent"].sum()))
    write_parquet(out, "vacancies")
    a.save()
    print(f"\nwrote vacancies ({len(out)}); persistent={int(out['is_persistent'].sum())}, "
          f"types={tcounts}")


if __name__ == "__main__":
    main()
