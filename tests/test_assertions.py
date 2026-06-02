import pytest

import lib.assertions as A
from lib.assertions import within


def test_within():
    assert within(100, 100, 0.05)
    assert within(104, 100, 0.05)
    assert not within(106, 100, 0.05)


def test_hard_failure_exits_nonzero(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "REPORT_PATH", tmp_path / "build_report.json")
    a = A.Assertions("test")
    a.check("A-DEMO", False, "intentional hard failure")
    with pytest.raises(SystemExit) as exc:
        a.finalize()
    assert exc.value.code == 1


def test_warning_does_not_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "REPORT_PATH", tmp_path / "build_report.json")
    a = A.Assertions("test")
    a.warn("A-WARN", False, "non-fatal")
    a.finalize()  # must not raise
    assert (tmp_path / "build_report.json").exists()


def test_passing_checks_do_not_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(A, "REPORT_PATH", tmp_path / "build_report.json")
    a = A.Assertions("test")
    a.check("A-OK", True, "all good")
    a.finalize()  # must not raise
