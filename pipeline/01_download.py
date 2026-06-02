#!/usr/bin/env python
"""Step 1 — download the 4 live sources to raw/ with magic-byte validation,
a dated immutable snapshot, and a fetch manifest. Fail-safe: if a fresh
download fails, reuse the previous snapshot and mark the build degraded."""
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests

from lib.config import HTTP_HEADERS, MAGIC, RAW_FILES, SNAPSHOTS, URLS
from lib.io import sha256_file, write_json

MONTH = datetime.now(timezone.utc).strftime("%Y-%m")
SNAP_DIR = SNAPSHOTS / MONTH


def looks_valid(key: str, path: Path) -> tuple[bool, str]:
    head = path.read_bytes()[:512]
    magic = MAGIC.get(key)
    if magic is not None:
        return (head.startswith(magic), f"magic {head[:8]!r}")
    # text sources (html/geojson): must be non-empty text-ish
    lowered = head.lstrip().lower()
    if key == "okfo":
        ok = b"<" in head and (b"html" in lowered or b"<table" in lowered or b"<!doctype" in lowered)
        return (ok, f"html head {head[:32]!r}")
    if key == "osm":
        return (head.lstrip()[:1] in (b"{", b"["), f"json head {head[:16]!r}")
    return (len(head) > 0, "non-empty")


def fetch(key: str, url: str, dest: Path) -> dict:
    print(f"[{key}] GET {url}")
    r = requests.get(url, headers=HTTP_HEADERS, timeout=120, stream=True)
    status = r.status_code
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    if status == 200:
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 16):
                fh.write(chunk)
        ok, detail = looks_valid(key, tmp)
        if ok:
            tmp.replace(dest)
            SNAP_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, SNAP_DIR / dest.name)
            sha = sha256_file(dest)
            print(f"  -> {dest.name}  {dest.stat().st_size:,} bytes  ({detail})")
            return {"key": key, "url": url, "status": status, "bytes": dest.stat().st_size,
                    "sha256": sha, "ok": True, "detail": detail}
        tmp.unlink(missing_ok=True)
        detail = f"bad magic: {detail}"
    else:
        detail = f"HTTP {status}"

    # fail-safe: reuse previous snapshot if any
    prev = _latest_snapshot(dest.name)
    if prev is not None:
        shutil.copy2(prev, dest)
        print(f"  !! {detail} — reused previous snapshot {prev}")
        return {"key": key, "url": url, "status": status, "bytes": dest.stat().st_size,
                "sha256": sha256_file(dest), "ok": False, "degraded": True,
                "detail": f"{detail}; reused {prev.parent.name}"}
    raise SystemExit(f"[{key}] download failed ({detail}) and no previous snapshot to fall back on")


def _latest_snapshot(filename: str) -> Path | None:
    candidates = sorted(SNAPSHOTS.glob(f"*/{filename}"))
    candidates = [c for c in candidates if c.parent != SNAP_DIR]
    return candidates[-1] if candidates else None


def main():
    manifest = {"fetched_at": datetime.now(timezone.utc).isoformat(), "month": MONTH, "files": []}
    degraded = False
    for key, url in URLS.items():
        rec = fetch(key, url, RAW_FILES[key])
        degraded = degraded or rec.get("degraded", False)
        manifest["files"].append(rec)
    manifest["degraded"] = degraded
    write_json(RAW_FILES["active"].parent / "fetch_manifest.json", manifest)
    print(f"\nfetch manifest written; degraded={degraded}")


if __name__ == "__main__":
    main()
