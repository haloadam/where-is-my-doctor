"""Build-time assertion framework. Hard checks fail the build (exit 1);
warn checks are reported but non-fatal. Each step records into a shared
report file so 07_emit can re-run / summarise the full suite."""
from __future__ import annotations

import sys

from lib.config import PROCESSED
from lib.io import read_json, write_json

REPORT_PATH = PROCESSED / "build_report.json"


def _load() -> dict:
    if REPORT_PATH.exists():
        return read_json(REPORT_PATH)
    return {"checks": [], "degraded": False, "stats": {}}


class Assertions:
    """Collect check results, persist to build_report.json, fail on hard miss."""

    def __init__(self, step: str):
        self.step = step
        self.report = _load()

    def _add(self, name, ok, detail, hard):
        self.report["checks"] = [c for c in self.report["checks"] if c["name"] != name]
        self.report["checks"].append(
            {"name": name, "ok": bool(ok), "hard": hard, "step": self.step, "detail": str(detail)}
        )
        tag = "OK " if ok else ("FAIL" if hard else "WARN")
        print(f"  [{tag}] {name}: {detail}")

    def check(self, name, ok, detail="", hard=True):
        self._add(name, ok, detail, hard)
        return ok

    def warn(self, name, ok, detail=""):
        return self._add(name, ok, detail, hard=False)

    def stat(self, key, value):
        self.report.setdefault("stats", {})[key] = value

    def save(self):
        write_json(REPORT_PATH, self.report)

    def finalize(self):
        """Persist and exit(1) if any HARD check failed (call at end of 07)."""
        self.save()
        hard_fails = [c for c in self.report["checks"] if c["hard"] and not c["ok"]]
        warns = [c for c in self.report["checks"] if not c["hard"] and not c["ok"]]
        print(f"\n=== assertion summary: {len(self.report['checks'])} checks, "
              f"{len(hard_fails)} hard failures, {len(warns)} warnings ===")
        for c in hard_fails:
            print(f"  HARD FAIL: {c['name']} ({c['step']}) — {c['detail']}", file=sys.stderr)
        if hard_fails:
            sys.exit(1)


def within(value, expected, tol_frac) -> bool:
    """True if value is within tol_frac (fraction) of expected."""
    return abs(value - expected) <= expected * tol_frac
