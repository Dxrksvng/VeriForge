# Validation record — 21 September 2026

This record separates observed execution from implementation and future work. Local machine: macOS ARM64, Python 3.13.9, PostgreSQL 17, Docker Desktop, Ollama qwen3.5:9b. No cloud billing or real-money settlement was configured.

## Verified evidence

| Check | Observed result | Evidence |
| --- | --- | --- |
| Backend unit/integration | 33 passed, 2 dependency deprecation warnings | local pytest run |
| Session security | bootstrap isolation, signature tamper, expiry, role enforcement and revocation passed | tests/test_api.py |
| Audit integrity | existing events backfilled, HMAC chain VALID, UPDATE/DELETE rejected | `/api/audit/integrity`, tests/test_api.py |
| PostgreSQL concurrency | 24 simultaneous same-key requests created one payment | tests/test_finance_integration.py |
| Rollback/validation | pre-commit failure leaves no payment; invalid money rejected | backend suite |
| Authorization/evidence | invalid roles, self approval, tampered evidence/source rejected | backend suite |
| Security execution | baseline passed real Gitleaks, scoped Semgrep and Trivy | changes.evidence in PostgreSQL |
| Public-data replay | 500 payments, 0 failures, 0 imbalanced ledgers; two requests per row | artifacts/dataset-evaluation.json |
| Concurrent identities | 100/100 signed identities validated; p95 1,475.59 ms | artifacts/control-plane-load.json |
| Replay p95 | 52.96 ms per TWO-request scenario in recorded run | same report; sequential local workload |
| Frontend | final production build and desktop/mobile journey passed | artifacts/*.png |
| AI change lifecycle | actual AI repair passed all gates, deployed, then injected fault recovered by rollback | artifacts/lifecycle.json completed PASS |
| Backup | pg_dump restored into a new temporary database; 0 ledger imbalances | .local/backups/*.json |

Full model → repair → release → recovery acceptance is recorded incrementally in artifacts/lifecycle.json. Only a final completed/PASS step is a successful lifecycle run; earlier failed runs remain in database/audit. The latest status is reconciled in PROGRESS.md after execution.

## Failures discovered, not hidden

- A generated patch accepted float amounts. Trusted financial tests blocked it.
- A repair used a forbidden isinstance() call. Capability policy blocked it. Repair context now includes all failed checks, not only financial assertions.
- An early Gitleaks stdout report was empty. Adapter now reads the scanner's report file; empty/malformed output cannot pass.
- Trivy found HIGH vulnerabilities in unused pip-vendored packages in the target base. The standard-library-only runtime now removes the unused installer packages; required scans then passed.
- A Docker build timed out. The change was INCONCLUSIVE, not released. Retrying after unloading the local model completed the build.
- Docker's OCI index identifier differed from the platform config identifier reported by Trivy. The adapter binds both through the exact Docker-exported archive. See [OCI image manifest specification](https://specs.opencontainers.org/image-spec/manifest/).
- After Docker restart, the durable ACTIVE release initially pointed at an exited container. Startup reconciliation now restarts the exact recorded image and updates its port; the 31-test run passed this behavior.
- When Ollama is unavailable, incident diagnosis now returns a retryable HTTP 503 instead of an opaque 500. A live AI diagnosis was not re-run after the final resource-pressure event; prior lifecycle Builder/Verifier calls were real and recorded.
- Machine free disk fell below 0.5 GB during the run. Do not treat this workstation as a reliable production host; leave several GB headroom before further model/image downloads.

## Data source and interpretation

[UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail), DOI 10.24432/C5BW33, CC BY 4.0. Source archive SHA-256 and retrieval time are recorded in the evaluation artifact. First 100 eligible positive non-cancelled line-item amounts are used; quantities × GBP unit price are mapped numerically into THB sandbox units WITHOUT exchange-rate conversion. No historical bank account reconstruction or fraud labels are claimed.

Source provenance: PUBLIC_BENCHMARK. Workload execution: SYNTHETIC_REPLAY. Real operational evidence: actual tests/scanners/model requests/deployments. Process-stop exercise: INJECTED_FAULT.

## Not demonstrated by these results

- No enterprise production deployment, SLA, real customer pilot or actual payment-provider settlement.
- No representative held-out bug benchmark, confidence interval, verifier recall/false-block generalization or distributed multi-host load. The 100-identity run is not 100 simultaneous LLM agents.
- Same local model for both roles: separate context/authority, not independent error distributions.
- Read-only GitHub PR adapter implemented and allowlist rejection tested; no authorized external repository configured and no hosted CI run.
- No external OIDC/ABAC service, distributed workload identity isolation, cloud IaC, cross-service tracing stack, multi-host HA or off-machine restore. Local sessions are signed, expiring and revocable.
- Local staged probes are not a traffic-split canary against live user traffic.
- Fixed trusted adversarial cases exist; the Verifier does not autonomously add executable test code.
- Incident storage and AI hypothesis adapter exist; cross-incident semantic retrieval and automated postmortem learning are not implemented.
- HMAC-chained append-only local audit is implemented, but is not an external attestation against an administrator holding the DB and signing key.
- Two dependency deprecation warnings remain in the TestClient stack; tests pass.

These boundaries preserve the larger roadmap rather than pretending all ten enterprise phases have been completed.
