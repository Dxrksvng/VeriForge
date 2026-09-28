"""Read-only, explicitly allowlisted GitHub PR import. No merge/write credentials."""

import base64
import hashlib
import os
import re

import httpx


def import_policy_pr(url):
    match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/([0-9]+)", url)
    if not match:
        raise ValueError("Use a GitHub pull request URL")
    repo, number = match.groups()
    allowlist = {r.strip() for r in os.getenv("VF_GITHUB_REPOS", "").split(",") if r.strip()}
    if repo not in allowlist:
        raise ValueError("Repository is not in VF_GITHUB_REPOS allowlist")
    with httpx.Client(
        base_url="https://api.github.com", timeout=20, headers={"Accept": "application/vnd.github+json"}
    ) as client:
        pr = client.get(f"/repos/{repo}/pulls/{number}")
        pr.raise_for_status()
        data = pr.json()
        files = client.get(f"/repos/{repo}/pulls/{number}/files", params={"per_page": 100})
        files.raise_for_status()
        if data["changed_files"] != 1 or [f["filename"] for f in files.json()] != ["policy.py"]:
            raise ValueError("Local v1 imports PRs changing only policy.py")
        head_repo = data["head"]["repo"]["full_name"]
        sha = data["head"]["sha"]
        content = client.get(f"/repos/{head_repo}/contents/policy.py", params={"ref": sha})
        content.raise_for_status()
        body = content.json()
        if body["size"] > 16000 or body["encoding"] != "base64":
            raise ValueError("Unsupported source size/encoding")
        source = base64.b64decode(body["content"]).decode()
    return {
        "title": data["title"],
        "source": source,
        "origin": {
            "repository": repo,
            "pull_request": int(number),
            "commit": sha,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        },
    }
