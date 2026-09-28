"""Resume a rejected real proposal after fixing integration; retain prior evidence."""

import argparse
import json
from datetime import datetime, timezone

from veriforge import ai, runtime, workflow
from veriforge.config import ROOT
from veriforge.db import connect

p = argparse.ArgumentParser()
p.add_argument("change_id")
args = p.parse_args()
artifact = ROOT / "artifacts/lifecycle.json"
results = json.loads(artifact.read_text())


def record(name, **data):
    results["steps"].append({"name": name, **data})
    artifact.write_text(json.dumps(results, default=str, indent=2))
    print(name, json.dumps(data, default=str), flush=True)


with connect() as conn:
    previous = conn.execute("SELECT * FROM changes WHERE id=%s", (args.change_id,)).fetchone()
assert previous and previous["status"] == "BLOCKED"
record("resume_after_repair_context_fix", at=datetime.now(timezone.utc).isoformat(), parent=previous["id"])
proposal = ai.repair(previous["source"], previous["evidence"], previous["review"])
row = workflow.create_change(proposal["title"], previous["requirement"], proposal["source"], "builder-model")
workflow.queue_verification(row["id"], "verifier-local")
while True:
    workflow.work_once()
    with connect() as conn:
        row = conn.execute("SELECT * FROM changes WHERE id=%s", (row["id"],)).fetchone()
    if row["status"] not in ("QUEUED", "VERIFYING"):
        break
record("ai_repair_full_context", id=row["id"], status=row["status"], review=row["review"])
assert row["status"] == "AWAITING_APPROVAL", row["evidence"]
workflow.approve(row["id"], "operator-local")
dep = runtime.deploy(row["id"], "deployer-local")
record("ai_release", id=dep["id"], status=dep["status"], metrics=dep["metrics"])
assert dep["status"] == "ACTIVE"
recovery = runtime.observe(dep["id"], "operator-local", inject=True)
record("runtime_recovery", **recovery)
assert recovery["recovery"]["error_rate"] == 0
record("completed", status="PASS")
