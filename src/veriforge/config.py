import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / ".local"


def config() -> dict:
    path = LOCAL / "config.json"
    if not path.exists():
        raise RuntimeError("Run python3 scripts/bootstrap.py before starting VeriForge")
    return json.loads(path.read_text())


def database_url() -> str:
    return os.getenv("VF_DATABASE_URL") or (
        "postgresql://veriforge:" + config()["database_password"] + "@127.0.0.1:55432/veriforge"
    )
