#!/usr/bin/env python
"""Step 4 — parse the KSH Helységnévtár gazetteer into the CANONICAL settlement
universe (population + KSH code, the join key for everything else).

Budapest reconciliation (the #1 risk, resolved against the real file):
the gazetteer lists 23 "Budapest NN. ker." rows PLUS a single "Budapest" parent
(code 13578, population = sum of kerületek). col-K and OSM admin_level=8 disagree
on granularity: col-K uses the 23 kerület codes; OSM has ONE "Budapest" polygon.
We aggregate to ONE Budapest unit (the parent 13578) — drop the 23 kerület rows,
keep the parent — which makes the universe 3,155 and matches the OSM polygon set
exactly. A kerület->13578 remap is emitted for 06 to fold kerület memberships in."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

from lib.assertions import Assertions, within
from lib.config import EXPECT, RAW_FILES
from lib.io import write_parquet
from lib.ksh import zfill5
from lib.names import normalize

SHEET = "Helységek 2025.01.01."
KER_RE = re.compile(r"^Budapest \d\d\. ker\.")
BUDAPEST_CODE = "13578"
# Positional columns in the gazetteer (header on row index 2 -> skiprows=2).
GCOL = dict(name=0, code=1, legal=2, county=3, population=10)


def main():
    a = Assertions("04_parse_ksh")
    g = pd.read_excel(RAW_FILES["ksh"], sheet_name=SHEET,
                      skiprows=2, header=0, dtype=str)
    g = g.iloc[:, [GCOL["name"], GCOL["code"], GCOL["legal"], GCOL["county"], GCOL["population"]]]
    g.columns = ["name", "code", "legal_status", "county", "population"]
    g["name"] = g["name"].astype("string").str.strip()
    g = g[g["name"].notna() & (g["name"] != "Összesen")].copy()

    g["ksh_code"] = g["code"].map(zfill5)
    n_all = len(g)
    a.check("A-KSH-ROWS", within(n_all, *EXPECT["KSH_ROWS"]),
            f"{n_all} gazetteer settlements (incl. Budapest parent + kerületek)")

    # kerület -> Budapest parent remap (emitted for step 06).
    ker_mask = g["name"].str.match(KER_RE, na=False)
    ker_codes = g.loc[ker_mask, "ksh_code"].tolist()
    remap = pd.DataFrame({"raw_code": ker_codes, "canonical_code": BUDAPEST_CODE})
    a.check("A-BUDAPEST-KER", len(ker_codes) == 23, f"{len(ker_codes)} Budapest kerület rows")

    # Canonical universe: drop the 23 kerület rows, keep the single Budapest parent.
    canon = g[~ker_mask].copy()
    canon["population"] = pd.to_numeric(canon["population"], errors="coerce").astype("Int64")
    canon["name_norm"] = canon["name"].map(normalize)
    canon = canon[["ksh_code", "name", "name_norm", "county", "legal_status", "population"]]
    canon = canon.drop_duplicates(subset=["ksh_code"]).reset_index(drop=True)

    a.check("A-CANON-UNIVERSE", canon["ksh_code"].is_unique, f"{len(canon)} canonical settlements")
    a.stat("settlement_count", len(canon))
    a.stat("budapest_population", int(canon.loc[canon["ksh_code"] == BUDAPEST_CODE, "population"].iloc[0]))

    write_parquet(canon, "settlements_ksh")
    write_parquet(remap, "code_remap")
    a.save()
    print(f"\nwrote settlements_ksh ({len(canon)} canonical) + code_remap "
          f"({len(remap)} kerület->Budapest)")


if __name__ == "__main__":
    main()
