import os

from dotenv import load_dotenv

load_dotenv()


def _get_bool_env(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    def __init__(self):
        self.DB_HOST = os.getenv("DB_HOST")
        self.DB_PORT = int(os.getenv("DB_PORT", "5432"))
        self.DB_NAME = os.getenv("DB_NAME")
        self.DB_USER = os.getenv("DB_USER")
        self.DB_PASSWORD = os.getenv("DB_PASSWORD")
        self.SECRET_KEY = os.getenv("SECRET_KEY")
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(
            os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        )
        self.ALLOW_LEGACY_TOKEN_HEADER = _get_bool_env(
            "ALLOW_LEGACY_TOKEN_HEADER",
            default=False,
        )
        self.CORS_ALLOW_ORIGINS = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ALLOW_ORIGINS",
                "http://localhost:5173,http://127.0.0.1:5173",
            ).split(",")
            if origin.strip()
        ]

    def validate_database(self):
        missing = [
            name
            for name, value in (
                ("DB_HOST", self.DB_HOST),
                ("DB_NAME", self.DB_NAME),
                ("DB_USER", self.DB_USER),
                ("DB_PASSWORD", self.DB_PASSWORD),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Database settings are incomplete: {', '.join(missing)}"
            )

    def require_secret_key(self) -> str:
        secret_key = (self.SECRET_KEY or "").strip()
        if not secret_key:
            raise RuntimeError("SECRET_KEY must be configured")

        if len(secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters long")

        return secret_key

    def validate_runtime(self):
        self.validate_database()
        self.require_secret_key()
        if self.ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
            raise RuntimeError(
                "ACCESS_TOKEN_EXPIRE_MINUTES must be greater than zero"
            )
        if "*" in self.CORS_ALLOW_ORIGINS:
            raise RuntimeError(
                "CORS_ALLOW_ORIGINS cannot contain '*' when credentials are enabled"
            )


settings = Settings()
