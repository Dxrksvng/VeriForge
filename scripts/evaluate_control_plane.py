"""Measure concurrent local control-plane reads with 100 distinct signed identities."""

import asyncio
import json
import statistics
import time
from datetime import datetime, timezone

import httpx

from veriforge.config import ROOT
from veriforge.identity import Principal, issue_session

BASE_URL = "http://127.0.0.1:8123"
IDENTITIES = 100


async def request(client, number):
    role = ("operator", "builder", "verifier", "deployer", "viewer")[number % 5]
    token = issue_session(Principal(f"load-{role}-{number}", role, "demo"))
    started = time.monotonic()
    response = await client.get(
        "/api/me",
        headers={"Authorization": "Bearer " + token},
    )
    elapsed = (time.monotonic() - started) * 1000
    body = response.json()
    return {
        "status": response.status_code,
        "identity_match": body.get("id") == f"load-{role}-{number}",
        "role_match": body.get("role") == role,
        "duration_ms": elapsed,
    }


async def main():
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=20, limits=limits) as client:
        started = time.monotonic()
        results = await asyncio.gather(*(request(client, number) for number in range(IDENTITIES)))
        wall_ms = (time.monotonic() - started) * 1000
    durations = sorted(item["duration_ms"] for item in results)
    successful = sum(
        item["status"] == 200 and item["identity_match"] and item["role_match"] for item in results
    )
    report = {
        "name": "Local signed-identity concurrency",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "provenance": "SYNTHETIC_LOAD",
        "identities": IDENTITIES,
        "requests": IDENTITIES,
        "successful": successful,
        "failures": IDENTITIES - successful,
        "wall_ms": round(wall_ms, 2),
        "p50_ms": round(statistics.median(durations), 2),
        "p95_ms": round(durations[int(IDENTITIES * 0.95) - 1], 2),
        "limitations": [
            "One local process and one workstation",
            "Read-only /api/me workload; not 100 simultaneous LLM generations",
            "Measures session validation and PostgreSQL registry lookup, not multi-host scalability",
        ],
    }
    destination = ROOT / "artifacts/control-plane-load.json"
    destination.write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
    if successful != IDENTITIES:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
