"""Back up application DB; restore into a NEW validation database, never over live data."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from uuid import uuid4

from veriforge.config import LOCAL


def run(*args, **kwargs):
    return subprocess.run(["docker", "exec", *args], check=True, capture_output=True, **kwargs)


def backup(check_restore=False):
    folder = LOCAL / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    filename = folder / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".dump")
    result = run("veriforge-db-1", "pg_dump", "-U", "veriforge", "-Fc", "veriforge")
    filename.write_bytes(result.stdout)
    filename.chmod(0o600)
    report = {
        "path": str(filename),
        "sha256": hashlib.sha256(result.stdout).hexdigest(),
        "bytes": len(result.stdout),
        "restore_verified": False,
    }
    if check_restore:
        name = "vf_restore_" + uuid4().hex[:12]
        run("veriforge-db-1", "createdb", "-U", "veriforge", name)
        try:
            run(
                "-i",
                "veriforge-db-1",
                "pg_restore",
                "-U",
                "veriforge",
                "--exit-on-error",
                "-d",
                name,
                input=result.stdout,
            )
            sql = "SELECT (SELECT count(*) FROM payments),(SELECT count(*) FROM changes),(SELECT count(*) FROM audit)"
            restored = (
                run("veriforge-db-1", "psql", "-U", "veriforge", "-d", name, "-Atc", sql)
                .stdout.decode()
                .strip()
            )
            live = (
                run("veriforge-db-1", "psql", "-U", "veriforge", "-d", "veriforge", "-Atc", sql)
                .stdout.decode()
                .strip()
            )
            invariant_sql = """SELECT count(*) FROM (
                SELECT p.id FROM payments p LEFT JOIN postings x ON x.payment_id=p.id
                GROUP BY p.id HAVING count(x.kind)<>3 OR coalesce(sum(x.delta),0)<>0
                ) invalid"""
            invalid = int(
                run("veriforge-db-1", "psql", "-U", "veriforge", "-d", name, "-Atc", invariant_sql)
                .stdout.decode()
                .strip()
            )
            if invalid:
                raise RuntimeError("Restored ledger violates financial invariants")
            report.update(
                restore_verified=True,
                restored_counts=restored,
                live_counts=live,
                ledger_imbalances=invalid,
                validation_database=name,
            )
        finally:
            # Only the just-created, random validation database is removed.
            run("veriforge-db-1", "dropdb", "-U", "veriforge", name)
    filename.with_suffix(".json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--verify-restore", action="store_true")
    backup(p.parse_args().verify_restore)
