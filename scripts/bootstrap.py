"""Generate local-only credentials once. Never print them in build logs."""

import json
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
local = root / ".local"
local.mkdir(mode=0o700, exist_ok=True)
target = local / "config.json"
if not target.exists():
    data = {
        "database_password": secrets.token_urlsafe(24),
        "signing_key": secrets.token_hex(32),
        "users": {
            role: secrets.token_urlsafe(24)
            for role in ("operator", "builder", "verifier", "deployer", "viewer")
        },
    }
    with target.open("x") as f:
        os.chmod(target, 0o600)
        json.dump(data, f, indent=2)
data = json.loads(target.read_text())
env = local / "compose.env"
env.write_text("VF_DB_PASSWORD=" + data["database_password"] + "\n")
os.chmod(env, 0o600)
print("Local credentials ready in .local/config.json (not printed).")
