"""Small IO helpers: parquet between steps, JSON, sha256, raw snapshots."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from lib.config import INTERIM


def write_parquet(df: pd.DataFrame, name: str) -> Path:
    path = INTERIM / f"{name}.parquet"
    df.to_parquet(path, index=False)
    return path


def read_parquet(name: str) -> pd.DataFrame:
    return pd.read_parquet(INTERIM / f"{name}.parquet")


def write_json(path: Path, obj, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=indent, default=str)
        fh.write("\n")


def read_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
