import unittest
from unittest.mock import patch

from app.core.config import settings


class ConfigTests(unittest.TestCase):
    def test_validate_runtime_rejects_wildcard_cors_with_credentials(self):
        with (
            patch.object(settings, "DB_HOST", "localhost"),
            patch.object(settings, "DB_NAME", "lal"),
            patch.object(settings, "DB_USER", "lal_user"),
            patch.object(settings, "DB_PASSWORD", "lal_password"),
            patch.object(settings, "SECRET_KEY", "test-secret-key-with-at-least-32-chars"),
            patch.object(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 60),
            patch.object(settings, "CORS_ALLOW_ORIGINS", ["*"]),
        ):
            with self.assertRaises(RuntimeError) as context:
                settings.validate_runtime()

        self.assertEqual(
            str(context.exception),
            "CORS_ALLOW_ORIGINS cannot contain '*' when credentials are enabled",
        )
