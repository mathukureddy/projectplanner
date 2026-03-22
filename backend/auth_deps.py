"""FastAPI dependencies for JWT bearer auth."""

from fastapi import Depends, Header, HTTPException

from auth_utils import decode_token


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    return parts[1].strip()


def get_token_payload(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer(authorization)
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


def require_admin(payload: dict = Depends(get_token_payload)) -> dict:
    if str(payload.get("role", "")).lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload
