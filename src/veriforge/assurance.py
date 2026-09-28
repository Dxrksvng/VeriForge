"""Bounded source verification, isolated execution and signed evidence."""

import ast
import hashlib
import hmac
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from veriforge.config import ROOT, config
from veriforge.scanners import image_scan, source_scans

POLICY_VERSION = "local-v2"
REQUIREMENT = (
    "Implement fee_minor(amount_minor): positive integer only, 1% fee rounded half up "
    "to minor units. Implement should_post(existing_payload,incoming_payload): True only "
    "when existing_payload is None; False for identical replay; raise ValueError on conflict."
)


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def signature(evidence):
    return hmac.new(
        bytes.fromhex(config()["signing_key"]),
        json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode(),
        hashlib.sha256,
    ).hexdigest()


def valid_signature(evidence, mac):
    return bool(evidence and mac and hmac.compare_digest(signature(evidence), mac))


def inspect_source(source):
    """Capability allowlist, not a claim to replace Semgrep/Trivy/Gitleaks."""
    if len(source) > 16000:
        return ["Source exceeds 16 KB"]
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"Syntax: {e.msg}"]
    errors = []
    functions = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    if functions != {"fee_minor", "should_post"}:
        errors.append("Exactly fee_minor and should_post required")
    for n in tree.body:
        if not isinstance(n, ast.FunctionDef):
            errors.append("Only function definitions allowed at module scope")
        elif n.decorator_list or n.args.defaults or n.args.kw_defaults:
            errors.append("Decorators/default arguments forbidden")
    for n in ast.walk(tree):
        if isinstance(
            n,
            (
                ast.Import,
                ast.ImportFrom,
                ast.Attribute,
                ast.Global,
                ast.Nonlocal,
                ast.ClassDef,
                ast.Lambda,
                ast.AsyncFunctionDef,
                ast.With,
            ),
        ):
            errors.append(f"Forbidden capability: {type(n).__name__}")
        if isinstance(n, ast.Name) and n.id.startswith("_"):
            errors.append("Private/dunder names forbidden")
        if isinstance(n, ast.Call) and (
            not isinstance(n.func, ast.Name) or n.func.id not in {"type", "int", "ValueError"}
        ):
            errors.append("Only type(), int(), ValueError() calls allowed")
    return sorted(set(errors))


def docker(*args, timeout=120):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-2000:])
    return result.stdout.strip()


def verify(source):
    start = time.monotonic()
    evidence = {
        "source_digest": digest(source),
        "policy_version": POLICY_VERSION,
        "provenance": "REAL_OPERATIONAL",
        "run_id": str(uuid4()),
        "checks": [],
        "image_id": None,
        "suite_version": "financial-policy-v1",
        "harness_digest": digest((ROOT / "sandbox/harness.py").read_text()),
        "runtime_digest": digest((ROOT / "sandbox/server.py").read_text()),
    }
    errors = inspect_source(source)
    evidence["checks"].append(
        {"name": "python-capability-allowlist", "status": "FAIL" if errors else "PASS", "findings": errors}
    )
    if not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="veriforge-build-") as directory:
                root = Path(directory)
                for name in ("Dockerfile", "harness.py", "server.py"):
                    shutil.copy(ROOT / "sandbox" / name, root / name)
                (root / "policy.py").write_text(source)
                tag = "veriforge-candidate:" + evidence["source_digest"][:20]
                docker("build", "--network=none", "-t", tag, str(root), timeout=180)
                image = docker("image", "inspect", tag, "--format", "{{.Id}}")
                evidence["image_id"] = image
                evidence["checks"].extend(source_scans(root))
                evidence["checks"].append(image_scan(image, root))
                name = "vf-check-" + evidence["run_id"]
                try:
                    raw = docker(
                        "run",
                        "--rm",
                        "--name",
                        name,
                        "--network=none",
                        "--read-only",
                        "--cap-drop=ALL",
                        "--security-opt=no-new-privileges",
                        "--pids-limit=32",
                        "--memory=128m",
                        "--cpus=0.5",
                        image,
                        "python",
                        "harness.py",
                        timeout=25,
                    )
                    result = json.loads(raw)
                    tests = result["tests"]
                    expected_names = {
                        "FIN-RETRY-001",
                        "FIN-NEW-001",
                        "FIN-CONFLICT-001",
                        "FIN-AMOUNT-001",
                    } | {f"FIN-FEE-{a}" for a in (1, 49, 50, 99, 100, 12550, 99999, 100000000)}
                    if {t["name"] for t in tests} != expected_names or len(tests) != len(expected_names):
                        raise ValueError("Incomplete test suite")
                    evidence["checks"].append(
                        {
                            "name": "financial-invariants",
                            "status": "PASS" if all(t["status"] == "PASS" for t in tests) else "FAIL",
                            "tests": tests,
                            "raw": raw,
                        }
                    )
                finally:
                    subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        except Exception as e:
            evidence["checks"].append(
                {"name": "financial-invariants", "status": "ERROR", "detail": str(e)[:2000]}
            )
    evidence["duration_ms"] = round((time.monotonic() - start) * 1000)
    evidence["decision"] = decision(evidence)
    return evidence, signature(evidence)


def decision(evidence):
    checks = evidence.get("checks", [])
    if any(c.get("status") == "FAIL" for c in checks):
        return "BLOCK"
    required = {"python-capability-allowlist", "financial-invariants", "gitleaks", "semgrep", "trivy"}
    if (
        evidence.get("policy_version") != POLICY_VERSION
        or not evidence.get("image_id")
        or {c.get("name") for c in checks} != required
    ):
        return "INCONCLUSIVE"
    return "PASS" if all(c.get("status") == "PASS" for c in checks) else "INCONCLUSIVE"
