import base64
import binascii
import hashlib
import hmac
import json
import secrets
import string
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import Depends, Header, HTTPException

from app.core.config import settings
from app.db.crud import crud


PASSWORD_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_VERSION = "v2"
PASSWORD_ITERATIONS = 390000
PASSWORD_SALT_BYTES = 16
PASSWORD_DIGEST_BYTES = hashlib.sha256().digest_size

ACCESS_TOKEN_VERSION = "v1"
ACCESS_TOKEN_TYPE = "access"
AUTHENTICATION_HEADERS = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class PasswordHashMetadata:
    iterations: int
    salt_bytes: bytes
    digest_bytes: bytes
    is_legacy: bool


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: int
    issued_at: int
    expires_at: int


class TokenValidationError(Exception):
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(detail)
        self.detail = detail


class ExpiredTokenError(TokenValidationError):
    def __init__(self):
        super().__init__("Token expired")


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode((value + padding).encode("ascii"))
    except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
        raise ValueError("Invalid base64url data") from exc


def _is_lower_hex(value: str, expected_length: int) -> bool:
    return len(value) == expected_length and all(char in string.hexdigits for char in value)


def _encode_password_hash(iterations: int, salt_bytes: bytes, digest_bytes: bytes) -> str:
    return (
        f"{PASSWORD_SCHEME}$"
        f"{PASSWORD_HASH_VERSION}$"
        f"{iterations}$"
        f"{_urlsafe_b64encode(salt_bytes)}$"
        f"{_urlsafe_b64encode(digest_bytes)}"
    )


def _parse_password_hash(password_hash: str) -> PasswordHashMetadata:
    if not isinstance(password_hash, str):
        raise ValueError("Password hash must be a string")

    parts = password_hash.split("$")

    if len(parts) == 5:
        scheme, version, iterations_raw, salt_encoded, digest_encoded = parts
        if scheme != PASSWORD_SCHEME or version != PASSWORD_HASH_VERSION:
            raise ValueError("Unsupported password hash format")

        iterations = int(iterations_raw)
        if iterations <= 0:
            raise ValueError("Invalid PBKDF2 iteration count")

        salt_bytes = _urlsafe_b64decode(salt_encoded)
        digest_bytes = _urlsafe_b64decode(digest_encoded)
        if len(salt_bytes) < PASSWORD_SALT_BYTES:
            raise ValueError("Salt is too short")
        if len(digest_bytes) != PASSWORD_DIGEST_BYTES:
            raise ValueError("Unexpected digest length")

        return PasswordHashMetadata(
            iterations=iterations,
            salt_bytes=salt_bytes,
            digest_bytes=digest_bytes,
            is_legacy=False,
        )

    if len(parts) == 4:
        scheme, iterations_raw, salt, digest_hex = parts
        if scheme != PASSWORD_SCHEME:
            raise ValueError("Unsupported password hash scheme")

        iterations = int(iterations_raw)
        if iterations <= 0:
            raise ValueError("Invalid PBKDF2 iteration count")

        if not _is_lower_hex(salt, PASSWORD_SALT_BYTES * 2):
            raise ValueError("Unsupported legacy salt format")
        if not _is_lower_hex(digest_hex, PASSWORD_DIGEST_BYTES * 2):
            raise ValueError("Unsupported legacy digest format")

        return PasswordHashMetadata(
            iterations=iterations,
            salt_bytes=salt.encode("ascii"),
            digest_bytes=bytes.fromhex(digest_hex),
            is_legacy=True,
        )

    raise ValueError("Unsupported password hash structure")


def hash_password(password: str) -> str:
    salt_bytes = secrets.token_bytes(PASSWORD_SALT_BYTES)
    digest_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_bytes,
        PASSWORD_ITERATIONS,
    )
    return _encode_password_hash(PASSWORD_ITERATIONS, salt_bytes, digest_bytes)


DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def password_needs_rehash(password_hash: str) -> bool:
    try:
        metadata = _parse_password_hash(password_hash)
    except (TypeError, ValueError):
        return True

    if metadata.is_legacy:
        return True

    return metadata.iterations < PASSWORD_ITERATIONS


def verify_password(password: str, password_hash: str) -> bool:
    try:
        metadata = _parse_password_hash(password_hash)
    except (TypeError, ValueError):
        return False

    derived_digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        metadata.salt_bytes,
        metadata.iterations,
    )
    return hmac.compare_digest(derived_digest, metadata.digest_bytes)


def _token_signing_key() -> bytes:
    return settings.require_secret_key().encode("utf-8")


def _sign_token(version: str, payload: str) -> str:
    signature = hmac.new(
        _token_signing_key(),
        f"{version}.{payload}".encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _urlsafe_b64encode(signature)


def create_token(user_id: int) -> str:
    if user_id <= 0:
        raise ValueError("User id must be a positive integer")

    issued_at = int(time.time())
    payload = {
        "exp": issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "iat": issued_at,
        "sub": str(user_id),
        "typ": ACCESS_TOKEN_TYPE,
        "ver": ACCESS_TOKEN_VERSION,
    }
    payload_part = _urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    return f"{ACCESS_TOKEN_VERSION}.{payload_part}.{_sign_token(ACCESS_TOKEN_VERSION, payload_part)}"


def validate_access_token(token: str) -> AccessTokenPayload:
    if not isinstance(token, str) or not token.strip():
        raise TokenValidationError()

    try:
        version, payload_part, signature_part = token.strip().split(".", 2)
    except ValueError:
        raise TokenValidationError() from None

    if version != ACCESS_TOKEN_VERSION:
        raise TokenValidationError()

    expected_signature = _sign_token(version, payload_part)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise TokenValidationError()

    try:
        payload = json.loads(_urlsafe_b64decode(payload_part))
    except (ValueError, json.JSONDecodeError):
        raise TokenValidationError() from None

    if not isinstance(payload, dict):
        raise TokenValidationError()

    if payload.get("typ") != ACCESS_TOKEN_TYPE or payload.get("ver") != ACCESS_TOKEN_VERSION:
        raise TokenValidationError()

    try:
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise TokenValidationError() from None

    now = int(time.time())
    if user_id <= 0 or issued_at <= 0 or expires_at <= issued_at:
        raise TokenValidationError()
    if issued_at > now + 300:
        raise TokenValidationError()
    if expires_at <= now:
        raise ExpiredTokenError()

    return AccessTokenPayload(
        user_id=user_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def extract_token(
    authorization: Optional[str] = None,
    legacy_token: Optional[str] = None,
) -> Optional[str]:
    if authorization:
        scheme, _, value = authorization.strip().partition(" ")
        if scheme.lower() != "bearer" or not value.strip():
            raise TokenValidationError()
        return value.strip()

    if settings.ALLOW_LEGACY_TOKEN_HEADER and legacy_token and legacy_token.strip():
        return legacy_token.strip()

    return None


def _authentication_error(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers=AUTHENTICATION_HEADERS)


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    legacy_token: Optional[str] = Header(default=None, alias="token"),
) -> dict[str, Any]:
    try:
        raw_token = extract_token(authorization=authorization, legacy_token=legacy_token)
    except TokenValidationError as exc:
        raise _authentication_error(exc.detail) from exc

    if not raw_token:
        raise _authentication_error("Not authenticated")

    try:
        token_payload = validate_access_token(raw_token)
    except ExpiredTokenError as exc:
        raise _authentication_error(exc.detail) from exc
    except TokenValidationError as exc:
        raise _authentication_error(exc.detail) from exc

    user = await crud.get_user_by_id(token_payload.user_id)
    if not user:
        raise _authentication_error("Invalid token")

    return user


async def get_current_user_id(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> int:
    return int(current_user["id"])
