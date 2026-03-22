import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional


def _secret() -> str:
    return os.getenv("AUTH_SECRET", "projectplanner-dev-secret")


def hash_password(password: str) -> str:
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == (hashed or "")


def create_token(username: str, role: str, expires_in_seconds: int = 60 * 60 * 24) -> str:
    payload = {
        "username": username,
        "role": role,
        "exp": int(time.time()) + int(expires_in_seconds),
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_secret().encode("utf-8"), body, hashlib.sha256).hexdigest().encode("utf-8")
    return base64.urlsafe_b64encode(body).decode("utf-8") + "." + sig.decode("utf-8")


def decode_token(token: str) -> Optional[dict]:
    if not token or "." not in token:
        return None
    body_b64, sig_hex = token.split(".", 1)
    try:
        body = base64.urlsafe_b64decode(body_b64.encode("utf-8"))
    except Exception:
        return None
    expected = hmac.new(_secret().encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig_hex):
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload

