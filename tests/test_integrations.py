import pytest

from veriforge.github_import import import_policy_pr
from veriforge.scanners import scan


def test_github_unallowlisted_rejected_without_network(monkeypatch):
    monkeypatch.delenv("VF_GITHUB_REPOS", raising=False)
    with pytest.raises(ValueError, match="allowlist"):
        import_policy_pr("https://github.com/example/repo/pull/1")
    with pytest.raises(ValueError, match="GitHub"):
        import_policy_pr("http://169.254.169.254/latest/meta-data/")


def test_scanner_timeout_is_error(monkeypatch):
    import subprocess

    def timeout(*args, **kwargs):
        if args[0][1] == "rm":
            return None
        raise subprocess.TimeoutExpired("scanner", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert scan("semgrep/semgrep:latest", [], lambda r: r)["status"] == "ERROR"
