import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Header, HTTPException

from veriforge.config import config

ISSUER = "veriforge-local"
AUDIENCE = "veriforge-api"
SESSION_TTL_SECONDS = 8 * 60 * 60


@dataclass(frozen=True)
class Principal:
    id: str
    role: str
    tenant: str = "demo"
    session_id: str | None = None


def _bearer(authorization: str) -> str:
    if not authorization.startswith("Bearer ") or not authorization[7:]:
        raise HTTPException(401, "Sign in with a local access token")
    return authorization[7:]


def authenticate_bootstrap(authorization: str = Header(default="")) -> Principal:
    """Authenticate a local credential only for session exchange."""
    candidate = hashlib.sha256(_bearer(authorization).encode()).digest()
    for role, token in config()["users"].items():
        if secrets.compare_digest(candidate, hashlib.sha256(token.encode()).digest()):
            return Principal(role + "-local", role)
    raise HTTPException(401, "Invalid local access token")


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except Exception as exc:
        raise HTTPException(401, "Invalid session token") from exc


def _sign(value: str) -> str:
    return _encode(hmac.new(str(config()["signing_key"]).encode(), value.encode(), hashlib.sha256).digest())


def issue_session(principal: Principal, *, now: int | None = None, ttl: int = SESSION_TTL_SECONDS) -> str:
    issued = int(time.time()) if now is None else now
    header = _encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims: dict[str, Any] = {
        "iss": ISSUER, "aud": AUDIENCE, "sub": principal.id, "role": principal.role,
        "tenant": principal.tenant, "iat": issued, "exp": issued + ttl,
        "jti": secrets.token_urlsafe(18),
    }
    payload = _encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
    unsigned = f"{header}.{payload}"
    token = f"{unsigned}.{_sign(unsigned)}"
    from veriforge.db import connect

    with connect() as conn:
        conn.execute(
            """INSERT INTO sessions(jti_hash,subject,role,tenant,issued_at,expires_at)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (
                hashlib.sha256(claims["jti"].encode()).hexdigest(), principal.id, principal.role,
                principal.tenant, datetime.fromtimestamp(issued, timezone.utc),
                datetime.fromtimestamp(issued + ttl, timezone.utc),
            ),
        )
    return token


def authenticate(authorization: str = Header(default="")) -> Principal:
    token = _bearer(authorization)
    try:
        header, payload, signature = token.split(".")
    except ValueError as exc:
        raise HTTPException(401, "Exchange the local access token for a session") from exc
    unsigned = f"{header}.{payload}"
    if not secrets.compare_digest(signature, _sign(unsigned)):
        raise HTTPException(401, "Invalid session signature")
    try:
        metadata = json.loads(_decode(header))
        claims = json.loads(_decode(payload))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(401, "Invalid session token") from exc
    now = int(time.time())
    if metadata != {"alg": "HS256", "typ": "JWT"}:
        raise HTTPException(401, "Unsupported session token")
    if claims.get("iss") != ISSUER or claims.get("aud") != AUDIENCE:
        raise HTTPException(401, "Session issuer or audience is invalid")
    if not isinstance(claims.get("exp"), int) or claims["exp"] <= now:
        raise HTTPException(401, "Session expired")
    if not isinstance(claims.get("iat"), int) or claims["iat"] > now + 30:
        raise HTTPException(401, "Session issue time is invalid")
    role = claims.get("role")
    if role not in config()["users"]:
        raise HTTPException(401, "Session role is invalid")
    if not all(isinstance(claims.get(key), str) and claims[key] for key in ("sub", "tenant", "jti")):
        raise HTTPException(401, "Session claims are incomplete")
    from veriforge.db import connect

    with connect() as conn:
        session = conn.execute(
            """SELECT subject,role,tenant,revoked_at,expires_at > now() AS active
               FROM sessions WHERE jti_hash=%s""",
            (hashlib.sha256(claims["jti"].encode()).hexdigest(),),
        ).fetchone()
    if (
        not session or session["revoked_at"] is not None or not session["active"]
        or session["subject"] != claims["sub"] or session["role"] != role
        or session["tenant"] != claims["tenant"]
    ):
        raise HTTPException(401, "Session is revoked or unknown")
    return Principal(claims["sub"], role, claims["tenant"], claims["jti"])


def revoke_session(principal: Principal) -> None:
    if not principal.session_id:
        raise HTTPException(401, "Session identifier missing")
    from veriforge.db import connect

    with connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked_at=now() WHERE jti_hash=%s AND revoked_at IS NULL",
            (hashlib.sha256(principal.session_id.encode()).hexdigest(),),
        )


def require(principal: Principal, *roles: str) -> None:
    if principal.role not in roles:
        raise HTTPException(403, "This identity cannot perform that action")
