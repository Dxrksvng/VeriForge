"""Real scanner processes. Missing tools or malformed reports fail closed."""

import hashlib
import json
import subprocess
import tarfile
from uuid import uuid4

from veriforge.config import LOCAL, ROOT

PINNED = {
    "zricethezav/gitleaks:latest": "zricethezav/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f",
    "semgrep/semgrep:latest": "semgrep/semgrep@sha256:34ab619bf1391a24bfda3f05debd0d8a6ce3093c2d5f9d39cfc00f83c1397823",
    "aquasec/trivy:latest": "aquasec/trivy@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969",
}


def scan(tool, args, parse, timeout=180, report_file=None):
    name = "vf-scan-" + uuid4().hex
    args = [PINNED.get(x, x) for x in args]
    try:
        result = subprocess.run(
            ["docker", "run", "--rm", "--name", name, *args], capture_output=True, text=True, timeout=timeout
        )
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr[-1200:])
        raw = json.loads(report_file.read_text() if report_file is not None else result.stdout)
        findings = parse(raw)
        if not isinstance(findings, list):
            raise ValueError("Scanner findings must be a list")
        if result.returncode == 1 and not findings:
            raise ValueError("Scanner exited unsuccessfully without a finding report")
        version = subprocess.run(
            ["docker", "image", "inspect", PINNED[tool], "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        return {
            "name": tool.split(":")[0].split("/")[-1],
            "status": "FAIL" if findings else "PASS",
            "tool_image": version,
            "findings": findings,
            "report": raw,
        }
    except Exception as e:
        return {"name": tool.split(":")[0].split("/")[-1], "status": "ERROR", "detail": str(e)[:1500]}
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)


def source_scans(directory):
    reports = directory / "reports"
    reports.mkdir()
    restricted = [
        "--network=none",
        "--read-only",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--memory=512m",
        "--tmpfs",
        "/tmp:rw,size=64m",
        "-v",
        str(directory) + ":/src:ro",
    ]
    gitleaks = scan(
        "zricethezav/gitleaks:latest",
        [
            *restricted,
            "-v",
            str(reports) + ":/out",
            "zricethezav/gitleaks:latest",
            "dir",
            "/src",
            "--no-banner",
            "--redact",
            "--report-format",
            "json",
            "--report-path",
            "/out/gitleaks.json",
        ],
        lambda r: r,
        report_file=reports / "gitleaks.json",
    )

    def semgrep_findings(r):
        if r.get("errors"):
            raise RuntimeError("Semgrep could not complete all requested rules")
        if not r.get("paths", {}).get("scanned"):
            raise RuntimeError("Semgrep scanned no files")
        return [{"rule": x["check_id"], "path": x["path"], "line": x["start"]["line"]} for x in r["results"]]

    semgrep = scan(
        "semgrep/semgrep:latest",
        [
            *restricted,
            "-e",
            "SEMGREP_SEND_METRICS=off",
            "-e",
            "HOME=/tmp",
            "-v",
            str(ROOT / "security/semgrep.yaml") + ":/rules.yaml:ro",
            "semgrep/semgrep:latest",
            "semgrep",
            "scan",
            "--config",
            "/rules.yaml",
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "/src",
        ],
        semgrep_findings,
    )
    return [gitleaks, semgrep]


def image_scan(image, directory):
    archive = directory / "image.tar"
    subprocess.run(["docker", "save", "-o", str(archive), image], check=True, capture_output=True)
    # Docker's containerd store may identify an OCI index, while Trivy reports
    # its platform-specific config digest. Bind that digest to this exact export.
    with tarfile.open(archive) as exported:
        manifests = json.load(exported.extractfile("manifest.json"))
        if len(manifests) != 1:
            raise ValueError("Expected one runnable image in Docker export")
        config_bytes = exported.extractfile(manifests[0]["Config"]).read()
        config_digest = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
    cache = LOCAL / "trivy-cache"
    cache.mkdir(exist_ok=True)

    def vulnerabilities(r):
        if not r.get("Metadata"):
            raise RuntimeError("Trivy metadata missing")
        if r["Metadata"].get("ImageID") not in (image, config_digest):
            raise RuntimeError("Trivy report does not match release image ID")
        return [
            {
                "id": v["VulnerabilityID"],
                "package": v["PkgName"],
                "severity": v["Severity"],
                "fixed_version": v.get("FixedVersion", ""),
            }
            for x in r.get("Results", [])
            for v in x.get("Vulnerabilities", [])
        ]

    result = scan(
        "aquasec/trivy:latest",
        [
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--memory=768m",
            "-v",
            str(directory) + ":/work:ro",
            "-v",
            str(cache) + ":/cache",
            "aquasec/trivy:latest",
            "--cache-dir",
            "/cache",
            "image",
            "--input",
            "/work/image.tar",
            "--scanners",
            "vuln",
            "--severity",
            "HIGH,CRITICAL",
            "--format",
            "json",
            "--timeout",
            "3m",
        ],
        vulnerabilities,
        timeout=210,
    )
    result["release_image_id"] = image
    result["config_digest"] = config_digest
    return result
