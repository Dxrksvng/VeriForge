from veriforge import ai


def test_repair_preserves_capability_failure_and_omits_large_raw_reports(monkeypatch):
    captured = {}

    def build(issue, source):
        captured.update(issue=issue, source=source)
        return {"source": source}

    monkeypatch.setattr(ai, "build", build)
    ai.repair(
        "original",
        {
            "checks": [
                {"name": "semgrep", "status": "PASS", "report": "LARGE"},
                {"name": "python-capability-allowlist", "status": "FAIL", "findings": ["forbidden call"]},
            ]
        },
    )
    assert "forbidden call" in captured["issue"]
    assert "LARGE" not in captured["issue"]
    assert "isinstance() is FORBIDDEN" in captured["issue"]
    assert captured["source"] == "original"
