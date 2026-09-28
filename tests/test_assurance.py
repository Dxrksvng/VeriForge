from copy import deepcopy

import pytest
from fastapi import HTTPException

from veriforge.assurance import POLICY_VERSION, decision, digest, inspect_source, signature, valid_signature
from veriforge.config import ROOT
from veriforge.workflow import check_release


def test_capability_check_blocks_injection_and_import():
    source = (ROOT / "sandbox/policy_good.py").read_text()
    assert inspect_source(source) == []
    assert inspect_source("import os\n" + source)
    assert inspect_source(source + "\nprint('forged evidence')")
    assert inspect_source(source.replace("return False", "return getattr(int, '__class__')"))


def evidence():
    source = (ROOT / "sandbox/policy_good.py").read_text()
    return {
        "source_digest": digest(source),
        "harness_digest": digest((ROOT / "sandbox/harness.py").read_text()),
        "runtime_digest": digest((ROOT / "sandbox/server.py").read_text()),
        "policy_version": POLICY_VERSION,
        "image_id": "sha256:abc",
        "checks": [
            {"name": "gitleaks", "status": "PASS"},
            {"name": "semgrep", "status": "PASS"},
            {"name": "trivy", "status": "PASS"},
            {"name": "python-capability-allowlist", "status": "PASS"},
            {"name": "financial-invariants", "status": "PASS"},
        ],
    }


def test_missing_and_error_fail_closed():
    e = evidence()
    assert decision(e) == "PASS"
    e["checks"][1]["status"] = "ERROR"
    assert decision(e) == "INCONCLUSIVE"
    e["checks"].pop()
    assert decision(e) == "INCONCLUSIVE"


def test_evidence_tampering_detected():
    e = evidence()
    mac = signature(e)
    assert valid_signature(e, mac)
    tampered = deepcopy(e)
    tampered["image_id"] = "sha256:other"
    assert not valid_signature(tampered, mac)


def test_source_changed_after_verification_cannot_release():
    e = evidence()
    row = {
        "source": (ROOT / "sandbox/policy_good.py").read_text(),
        "digest": e["source_digest"],
        "evidence": e,
        "evidence_mac": signature(e),
        "image_id": e["image_id"],
        "policy_version": POLICY_VERSION,
        "review": {"verdict": "PASS"},
    }
    check_release(row)
    row["source"] += "\n# changed"
    with pytest.raises(HTTPException):
        check_release(row)
