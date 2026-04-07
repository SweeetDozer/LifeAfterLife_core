import hashlib
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.core import security


TEST_SECRET_KEY = "test-secret-key-with-at-least-32-chars"


def _make_legacy_password_hash(password: str, salt_hex: str, iterations: int) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_hex.encode("ascii"),
        iterations,
    )
    return f"{security.PASSWORD_SCHEME}${iterations}${salt_hex}${digest.hex()}"


class PasswordSecurityTests(unittest.TestCase):
    def test_password_hash_round_trip_and_rehash_flag(self):
        password_hash = security.hash_password("correct horse battery staple")

        self.assertTrue(
            security.verify_password("correct horse battery staple", password_hash)
        )
        self.assertFalse(security.verify_password("wrong password", password_hash))
        self.assertFalse(security.password_needs_rehash(password_hash))

    def test_legacy_password_hash_still_verifies_but_requires_rehash(self):
        legacy_hash = _make_legacy_password_hash(
            "legacy password",
            salt_hex="ab" * security.PASSWORD_SALT_BYTES,
            iterations=120000,
        )

        self.assertTrue(security.verify_password("legacy password", legacy_hash))
        self.assertFalse(security.verify_password("other password", legacy_hash))
        self.assertTrue(security.password_needs_rehash(legacy_hash))


class TokenSecurityTests(unittest.IsolatedAsyncioTestCase):
    def test_validate_access_token_accepts_token_created_by_create_token(self):
        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch.object(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            patch("app.core.security.time.time", return_value=1_700_000_000),
        ):
            token = security.create_token(42)
            payload = security.validate_access_token(token)

        self.assertEqual(payload.user_id, 42)
        self.assertEqual(payload.issued_at, 1_700_000_000)
        self.assertEqual(payload.expires_at, 1_700_000_000 + 15 * 60)

    def test_validate_access_token_rejects_tampered_payload(self):
        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch.object(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            patch("app.core.security.time.time", return_value=1_700_000_000),
        ):
            token = security.create_token(42)

        version, payload_part, signature_part = token.split(".")
        payload = json.loads(security._urlsafe_b64decode(payload_part))
        payload["sub"] = "999"
        tampered_payload_part = security._urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        tampered_token = ".".join((version, tampered_payload_part, signature_part))

        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch("app.core.security.time.time", return_value=1_700_000_000),
        ):
            with self.assertRaises(security.TokenValidationError):
                security.validate_access_token(tampered_token)

    def test_validate_access_token_rejects_future_issue_time(self):
        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch.object(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            patch("app.core.security.time.time", return_value=1_700_000_400),
        ):
            token = security.create_token(42)

        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch("app.core.security.time.time", return_value=1_700_000_000),
        ):
            with self.assertRaises(security.TokenValidationError):
                security.validate_access_token(token)

    async def test_get_current_user_accepts_legacy_token_header_when_enabled(self):
        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch.object(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            patch.object(security.settings, "ALLOW_LEGACY_TOKEN_HEADER", True),
            patch("app.core.security.time.time", return_value=1_700_000_000),
        ):
            token = security.create_token(7)

        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch.object(security.settings, "ALLOW_LEGACY_TOKEN_HEADER", True),
            patch("app.core.security.time.time", return_value=1_700_000_100),
            patch("app.core.security.crud") as crud_mock,
        ):
            crud_mock.get_user_by_id = AsyncMock(return_value={"id": 7, "email": "u@test"})

            user = await security.get_current_user(
                authorization=None,
                legacy_token=token,
            )

        self.assertEqual(user["id"], 7)
        crud_mock.get_user_by_id.assert_awaited_once_with(7)

    async def test_get_current_user_rejects_token_for_missing_user(self):
        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch.object(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            patch("app.core.security.time.time", return_value=1_700_000_000),
        ):
            token = security.create_token(7)

        with (
            patch.object(security.settings, "SECRET_KEY", TEST_SECRET_KEY),
            patch("app.core.security.time.time", return_value=1_700_000_100),
            patch("app.core.security.crud") as crud_mock,
        ):
            crud_mock.get_user_by_id = AsyncMock(return_value=None)

            with self.assertRaises(HTTPException) as context:
                await security.get_current_user(
                    authorization=f"Bearer {token}",
                    legacy_token=None,
                )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Invalid token")


if __name__ == "__main__":
    unittest.main()
