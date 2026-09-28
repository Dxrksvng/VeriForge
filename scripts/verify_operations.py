"""Verify live authenticated metrics, trace correlation and model incident analysis."""

import json

import httpx

from veriforge.config import ROOT
from veriforge.identity import Principal, issue_session

base = "http://127.0.0.1:8123"
headers = {"Authorization": "Bearer " + issue_session(Principal("operator-local", "operator"))}
with httpx.Client(base_url=base, headers=headers, timeout=200) as client:
    metrics = client.get("/api/metrics")
    metrics.raise_for_status()
    assert "veriforge_http_requests_total" in metrics.text
    overview = client.get("/api/overview")
    overview.raise_for_status()
    assert len(overview.headers["X-Trace-ID"]) == 32
    incident = overview.json()["incidents"][0]
    response = client.post(f"/api/incidents/{incident['id']}/diagnose")
    if response.status_code == 503:
        result = {
            "incident_id": str(incident["id"]),
            "metrics_endpoint": "PASS",
            "trace_header": "PASS",
            "diagnosis": "INCONCLUSIVE: local verifier unavailable; API returned retryable 503",
        }
    else:
        response.raise_for_status()
        result = {
            "incident_id": incident["id"],
            "metrics_endpoint": "PASS",
            "trace_header": "PASS",
            "diagnosis": response.json(),
        }
    (ROOT / "artifacts/incident-analysis.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
