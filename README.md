# VeriForge

### Evidence-driven assurance and recovery for AI-generated changes

VeriForge is a **local production simulation** for a narrow financial-policy workflow. It takes a proposed change through isolated checks, evidence review, a deterministic release gate, human approval, local Docker deployment, runtime monitoring, and recovery. All payments use test funds; the system is not connected to a bank or payment provider.

```text
Proposal → Trusted tests & scanners → Evidence-bound decision
         → Human approval → Local release → Monitor → Recover
```

## What works today

- **Financial lab:** PostgreSQL ledger with integer money, balanced postings, concurrent idempotency, and conflict rejection.
- **Change assurance:** Builder and Verifier use separate contexts; trusted financial tests, Gitleaks, Semgrep, and Trivy feed deterministic gates. A failed or missing mandatory check cannot become a pass.
- **Controlled release:** evidence binds the source, image, and checks; operator approval and deployer identity are separate. A worker handles leases and retries.
- **Recovery:** local Docker release is probed and monitored; an injected process-stop fault can trigger rollback or restart.
- **Operator view:** React dashboard, signed and revocable sessions, HMAC-chained local audit, metrics, and model usage.
- **Reproducible evaluation:** UCI Online Retail amounts are replayed as synthetic test payments with source/transform provenance; PostgreSQL backup is restored to a separate validation database.

The verified scope is **one local tenant and two financial-policy functions**. Builder and Verifier currently use the same local model with different contexts, so their errors are not statistically independent. See [validation evidence](docs/VALIDATION.md) for what was run and what those results do *not* establish.

## Run locally

Prerequisites: macOS ARM64 setup used for validation, Python 3.13, `uv`, Node 22, Docker Desktop, Ollama with `qwen3.5:9b`, and at least 3 GB free disk. First-time dependency, image, and dataset downloads need internet access; model calls run locally.

```sh
./run-local.sh
```

Open **http://127.0.0.1:8123**. Role-specific bootstrap credentials are generated in `.local/config.json`; keep that file private and never commit it. Sign-in exchanges a bootstrap credential for an expiring session, and sign-out revokes it. Follow the [runbook](docs/RUNBOOK.md) for the exact operator/deployer journey and safe shutdown.

To run the fast local checks after dependencies are installed:

```sh
.venv/bin/ruff check src tests scripts
.venv/bin/pytest -q
cd frontend && npm run build
```

The complete lifecycle verification and data replay commands are in the runbook. Those checks can start containers and use the local model; they are not required merely to read this repository.

## Example journey

1. Submit a failing policy proposal or load the test fixture.
2. Verify it. Inspect test, scanner, and artifact evidence; blocked/inconclusive results cannot be approved.
3. Approve an evidence-bound passing change as operator, then deploy it with the separate deployer identity.
4. Replay an idempotent test payment and observe the ledger result.
5. Inject a local process-stop fault and inspect the incident and recovery record.

This is a controlled lab. It does not execute arbitrary generated code on a production host and does not move real money.

## Architecture and evidence

| Document | Use it for |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Components, trust boundaries, and decision flow |
| [Runbook](docs/RUNBOOK.md) | Start, operate, verify, back up, and recover |
| [Validation](docs/VALIDATION.md) | Observed tests, failures, metrics, and limitations |
| [System guide (Thai)](docs/SYSTEM-GUIDE-TH.md) | Important functions and code paths |
| [Progress](docs/PROGRESS.md) | Latest local state and next action |
| [Learning roadmap](docs/LEARNING-ROADMAP.md) | Planned teaching modules; separate from engineering status |

## Boundaries

No enterprise SLA, real-money settlement, multi-host availability, external identity provider, off-machine backup, or third-party audit attestation has been demonstrated. The local audit chain can be recomputed by someone holding both its database and signing key. Treat benchmark replay, fault injection, and real scanner executions as different kinds of evidence.

VeriForge is an independent engineering project. Do not put real credentials, customer data, or production systems into this lab without a separate security and deployment review.
