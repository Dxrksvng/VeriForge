"""Actual Docker + local model lifecycle. No mocked successful reviews."""

import json
from datetime import datetime, timezone

from veriforge import ai, runtime, workflow
from veriforge.assurance import REQUIREMENT
from veriforge.config import ROOT
from veriforge.db import connect, migrate, seed_accounts

migrate()
seed_accounts()
results = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": []}


def record(name, **data):
    results["steps"].append({"name": name, **data})
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "lifecycle.json").write_text(json.dumps(results, default=str, indent=2))
    print(name, json.dumps(data, default=str), flush=True)


def verify_change(row):
    workflow.queue_verification(row["id"], "verifier-local")
    while True:
        workflow.work_once()
        with connect() as conn:
            current = conn.execute("SELECT * FROM changes WHERE id=%s", (row["id"],)).fetchone()
        if current["status"] not in ("QUEUED", "VERIFYING"):
            return current


bad = workflow.create_change(
    "Duplicate fee regression",
    REQUIREMENT,
    (ROOT / "sandbox/policy_bad.py").read_text(),
    "fixture-builder",
    "INJECTED_FAULT",
)
bad = verify_change(bad)
record("bad_patch", id=bad["id"], status=bad["status"])
assert bad["status"] == "BLOCKED", bad["evidence"]
good = workflow.create_change(
    "Trusted baseline release",
    REQUIREMENT,
    (ROOT / "sandbox/policy_good.py").read_text(),
    "fixture-builder",
    "SYNTHETIC_REPLAY",
)
good = verify_change(good)
record("baseline_verification", id=good["id"], status=good["status"], review=good["review"])
assert good["status"] == "AWAITING_APPROVAL", good["review"]
workflow.approve(good["id"], "operator-local")
dep = runtime.deploy(good["id"], "deployer-local")
record("baseline_deployed", id=dep["id"], status=dep["status"], metrics=dep["metrics"])
proposal = ai.build(
    "Fix the duplicate replay and half-up rounding bugs.", (ROOT / "sandbox/policy_bad.py").read_text()
)
generated = workflow.create_change(proposal["title"], REQUIREMENT, proposal["source"], "builder-model")
generated = verify_change(generated)
record("ai_patch", id=generated["id"], status=generated["status"], review=generated["review"])
for attempt in range(2):
    if generated["status"] != "BLOCKED":
        break
    proposal = ai.repair(generated["source"], generated["evidence"], generated["review"])
    generated = workflow.create_change(proposal["title"], REQUIREMENT, proposal["source"], "builder-model")
    generated = verify_change(generated)
    record(
        "ai_repair",
        attempt=attempt + 1,
        id=generated["id"],
        status=generated["status"],
        review=generated["review"],
    )
assert generated["status"] == "AWAITING_APPROVAL", generated["evidence"]
workflow.approve(generated["id"], "operator-local")
dep2 = runtime.deploy(generated["id"], "deployer-local")
record("ai_release", id=dep2["id"], status=dep2["status"], metrics=dep2["metrics"])
recovery = runtime.observe(dep2["id"], "operator-local", inject=True)
record("runtime_recovery", **recovery)
assert recovery["recovery"]["error_rate"] == 0
record("completed", status="PASS")
