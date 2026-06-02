#!/usr/bin/env python
"""Step 2 — parse the NEAK active-practices XLSX and EXPLODE the served-settlements
column (K) into a tidy (hsz_kod, ksh_code) membership table.

Columns are read BY POSITION (A–M) because header B has a source typo ("Szervezti").
KSH codes are kept as 5-digit zero-padded strings (782 distinct codes have leading zeros)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from lib.assertions import Assertions, within
from lib.config import EXPECT, RAW_FILES
from lib.io import write_parquet
from lib.ksh import parse_served_cell

# Positional column map (A..M).
COL = dict(county=0, hsz_kod=1, type=2, forma=3, neak_kod=4, provider=5,
           postal=6, seat_name=7, address=8, phone=9, served=10, jaras=11, gp_name=12)


def main():
    a = Assertions("02_parse_active")
    df = pd.read_excel(RAW_FILES["active"], sheet_name=0, header=0, dtype=str)
    df = df.iloc[:, : len(COL)]
    df.columns = list(COL.keys())
    df = df.dropna(subset=["hsz_kod"]).reset_index(drop=True)
    for c in df.columns:
        df[c] = df[c].astype("string").str.strip()

    n = len(df)
    a.check("A-ACTIVE-ROWS", within(n, *EXPECT["ACTIVE_ROWS"]), f"{n} rows (expect ~6367)")
    a.check("A-COUNTIES", df["county"].nunique() == EXPECT["COUNTIES"],
            f"{df['county'].nunique()} counties")
    hsz_ok = df["hsz_kod"].str.fullmatch(r"\d{9}").fillna(False)
    a.check("A-HSZ-FMT", hsz_ok.all() and df["hsz_kod"].is_unique,
            f"{(~hsz_ok).sum()} non-9-digit, unique={df['hsz_kod'].is_unique}")

    # Explode col K -> memberships.
    rows, parse_fail = [], 0
    for hsz, served in zip(df["hsz_kod"], df["served"].fillna("")):
        pairs, fails = parse_served_cell(served)
        parse_fail += fails
        rows.extend((hsz, code, name) for code, name in pairs)
    mem = pd.DataFrame(rows, columns=["hsz_kod", "ksh_code", "served_name"])
    mem = mem.drop_duplicates(subset=["hsz_kod", "ksh_code"]).reset_index(drop=True)

    a.check("A-KPARSE", parse_fail == 0, f"{parse_fail} col-K pair parse failures")
    code_ok = mem["ksh_code"].str.fullmatch(r"\d{5}").fillna(False)
    a.check("A-CODEFMT", code_ok.all(), f"{(~code_ok).sum()} non-5-digit codes")
    a.check("A-MEMBERSHIP", within(len(mem), *EXPECT["MEMBERSHIPS"]),
            f"{len(mem)} memberships (expect ~8147)")
    fanout = len(mem) / df["hsz_kod"].nunique()
    lo, hi = EXPECT["MEMBERSHIP_FANOUT"]
    a.check("A-MEMBERSHIP-FANOUT", lo <= fanout <= hi, f"mean {fanout:.3f} per körzet")
    a.stat("active_rows", n)
    a.stat("distinct_k_codes", int(mem["ksh_code"].nunique()))

    practices = df.copy()
    write_parquet(practices, "practices")
    write_parquet(mem, "practice_membership")
    a.save()
    print(f"\nwrote practices ({len(practices)}) + practice_membership ({len(mem)}), "
          f"{mem['ksh_code'].nunique()} distinct served settlements")


if __name__ == "__main__":
    main()
