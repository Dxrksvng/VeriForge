# Runbook — local operation

## Start

Prerequisites: Python 3.13, uv, Node 22, Docker Desktop running, Ollama with `qwen3.5:9b`. First dependency/image/dataset downloads need network access; model calls are local. Keep at least 3 GB free for scanners/builds.

From the project root:

```sh
./run-local.sh
```

Open `http://127.0.0.1:8123`. Local per-role bootstrap tokens are in `.local/config.json`; open this file privately and paste the appropriate token. Never share or commit it. The bootstrap credential is exchanged for an 8-hour signed session in sessionStorage; sign out revokes it in PostgreSQL. Operator approves and controls local lab experiments; deployer uses a different identity.

The start script creates credentials once, synchronizes the locked dependencies, starts PostgreSQL, builds the UI if absent, applies migrations, and runs the API, worker and runtime monitor. For changed frontend source run `cd frontend && npm ci && npm run build`, then restart the API. No public tunnel is configured.

## Main journey

1. Sign in as operator; open Changes and load a failing fixture or ask local AI for a proposal.
2. Open the change and select Verify. Worker performs real source/image scans and Docker acceptance tests.
3. A failure is BLOCKED; errors/missing reports are INCONCLUSIVE. Inspect the exact check before retrying. An AI repair is a new change, never an in-place replacement of approved source.
4. After all gates and AI review pass, operator approves the evidence-bound artifact.
5. Sign out and sign in as deployer; deploy the approved change. Local HTTP probes must pass before activation.
6. Sign in as operator; submit and replay a financial payment. PostgreSQL deduplicates it and checks the candidate quote against the trusted rule.
7. On Releases, observe traffic or inject a local process stop. The system records an incident and verifies rollback/restart. This uses test funds only.

## Verification commands

```sh
.venv/bin/ruff check src tests scripts
.venv/bin/pytest -q --junitxml=artifacts/tests.xml
env PYTHONPATH=src .venv/bin/python scripts/verify_lifecycle.py
env PYTHONPATH=src .venv/bin/python scripts/evaluate_data.py --limit 100
env PYTHONPATH=src .venv/bin/python scripts/backup.py --verify-restore
cd frontend && npm run build && node tests/browser.mjs
```

The lifecycle test calls a real model. A rejected patch is a valid safety outcome but not a successful end-to-end release run. Do not edit trusted tests to make a generated patch pass. Repair receives the failed evidence and is capped at two automated attempts in the lifecycle script.

## Incident handling

| Symptom | Check | Action |
| --- | --- | --- |
| UI cannot load API | API logs / health | Restart API; preserve database volume |
| Job queued | Worker process | Start worker; do not approve queued changes |
| VERIFYING stale | jobs lease/attempts | Expired lease is reclaimed; after 3 attempts state is INCONCLUSIVE |
| Scanner ERROR | Evidence detail + disk + scanner image/DB | Repair availability, then re-verify; never map error to pass |
| Model unavailable | Ollama service/model + daily call cap | Restore service or wait/reset configured budget deliberately; no silent fallback |
| Financial payment 503 | Active release health / quote | Recover release; existing idempotent result remains retrievable |
| Runtime regression | Release observations/incident timeline | Monitor rolls back to standby or restarts approved image; verify recovery metrics |
| Data loss concern | Last dump and checksum | Restore to a NEW database first; never overwrite live DB automatically |

## Backups and recovery limits

`scripts/backup.py --verify-restore` writes a custom PostgreSQL dump under `.local/backups/`, restores into a uniquely named validation DB, checks readable data and removes only that temporary DB. It never drops the application DB. Backups contain business/evidence data; keep permissions restricted.

Current backups are on the same machine. For machine-loss recovery, copy the dump and signing-key/credential configuration into an encrypted off-machine location that you control. No off-machine account is configured. Set backup frequency and retention based on your chosen RPO; no RPO/RTO or availability SLA has been measured/promised.

DB backup does not contain Docker images. Preserve or rebuild approved images and re-verify before releasing if artifact IDs differ. Archive traces separately if needed; their current local file is `.local/traces.jsonl`.

## Controls and bounded costs

- `VF_MODEL_DAILY_CALLS` defaults to 30; calls and actual tokens are recorded in PostgreSQL.
- `VF_BUILDER_MODEL` and `VF_VERIFIER_MODEL` default to installed `qwen3.5:9b`; separate prompts but same weights.
- `VF_OLLAMA_URL` defaults to localhost:11434. No cloud API spend is configured.
- `VF_DATABASE_URL` optionally overrides the generated local DB connection.
- `VF_GITHUB_REPOS` explicitly allowlists read-only imports such as `owner/repo`; the supported PR changes only `policy.py`. No GitHub write/merge token is used.
- Prometheus endpoint `/api/metrics` requires bearer auth. OpenTelemetry spans are written locally, not sent to a third party.

## Stop and preserve data

Ctrl+C the start script to stop API/worker/monitor. `docker compose --env-file .local/compose.env stop db` stops only this project's database. Release containers remain separately manageable by their recorded IDs. Never use broad Docker pruning or `down -v` as normal shutdown.

## Before public or real-money use

This release is a local production simulation, not a public multi-tenant financial service. Required upgrades include federated OIDC/workload identity, separate OS/service identities and execution hosts, HTTPS, rate limits and abuse controls, externally anchored evidence, off-machine recovery, appropriate compliance review, and actual settlement/reconciliation integration. These are explicit boundaries, not features implied by a successful local run.
