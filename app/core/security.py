import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 390000


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_SCHEME}${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def password_needs_rehash(password_hash: str) -> bool:
    return not password_hash.startswith(f"{PASSWORD_SCHEME}$")


def verify_password(password: str, password_hash: str) -> bool:
    if password_needs_rehash(password_hash):
        return hmac.compare_digest(password_hash, password)

    try:
        scheme, iterations, salt, stored_digest = password_hash.split("$", 3)
    except ValueError:
        return False

    if scheme != PASSWORD_SCHEME:
        return False

    derived_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        int(iterations),
    ).hex()
    return hmac.compare_digest(derived_digest, stored_digest)


def _sign_token(payload: str) -> str:
    signature = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _urlsafe_b64encode(signature)


def create_token(user_id: int) -> str:
    payload = {
        "sub": user_id,
        "exp": int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
    payload_part = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{payload_part}.{_sign_token(payload_part)}"


def get_user_by_token(token: str):
    try:
        payload_part, signature_part = token.split(".", 1)
    except ValueError:
        return None

    expected_signature = _sign_token(payload_part)
    if not hmac.compare_digest(signature_part, expected_signature):
        return None

    try:
        payload = json.loads(_urlsafe_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    return payload.get("sub")


def extract_token(
    authorization: Optional[str] = None,
    token: Optional[str] = None,
) -> Optional[str]:
    if token:
        return token.strip()

    if not authorization:
        return None

    scheme, _, value = authorization.partition(" ")
    if scheme.lower() == "bearer" and value:
        return value.strip()

    return authorization.strip()


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
    token: Optional[str] = Header(default=None),
) -> int:
    raw_token = extract_token(authorization=authorization, token=token)
    user_id = get_user_by_token(raw_token) if raw_token else None

    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return int(user_id)
