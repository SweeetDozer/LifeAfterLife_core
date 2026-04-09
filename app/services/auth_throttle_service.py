from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.config import settings
from app.db.crud import crud
from app.db.database import db


LOGIN_IP_KEY = "login_ip"
LOGIN_EMAIL_IP_KEY = "login_email_ip"
REGISTER_IP_KEY = "register_ip"

LOGIN_THROTTLE_DETAIL = "Too many authentication attempts. Try again later."
REGISTER_THROTTLE_DETAIL = "Too many registration attempts. Try again later."


@dataclass(frozen=True)
class ThrottlePolicy:
    limit: int
    window: timedelta
    lockout: timedelta


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _login_email_ip_key(email: str, client_ip: str) -> str:
    return f"{_normalize_email(email)}|{client_ip}"


def _retry_after_seconds(locked_until: datetime, now: datetime) -> int:
    return max(1, int((locked_until - now).total_seconds()))


class AuthThrottleService:
    @staticmethod
    def _login_ip_policy() -> ThrottlePolicy:
        return ThrottlePolicy(
            limit=settings.AUTH_LOGIN_IP_FAILURE_LIMIT,
            window=timedelta(minutes=settings.AUTH_LOGIN_THROTTLE_WINDOW_MINUTES),
            lockout=timedelta(minutes=settings.AUTH_LOGIN_LOCKOUT_MINUTES),
        )

    @staticmethod
    def _login_email_ip_policy() -> ThrottlePolicy:
        return ThrottlePolicy(
            limit=settings.AUTH_LOGIN_EMAIL_IP_FAILURE_LIMIT,
            window=timedelta(minutes=settings.AUTH_LOGIN_THROTTLE_WINDOW_MINUTES),
            lockout=timedelta(minutes=settings.AUTH_LOGIN_LOCKOUT_MINUTES),
        )

    @staticmethod
    def _register_ip_policy() -> ThrottlePolicy:
        window = timedelta(minutes=settings.AUTH_REGISTER_WINDOW_MINUTES)
        return ThrottlePolicy(
            limit=settings.AUTH_REGISTER_IP_ATTEMPT_LIMIT,
            window=window,
            lockout=window,
        )

    async def assert_login_allowed(self, client_ip: str, email: str):
        now = _utcnow()
        await self._assert_key_allowed(
            LOGIN_IP_KEY,
            client_ip,
            self._login_ip_policy(),
            LOGIN_THROTTLE_DETAIL,
            now=now,
        )
        await self._assert_key_allowed(
            LOGIN_EMAIL_IP_KEY,
            _login_email_ip_key(email, client_ip),
            self._login_email_ip_policy(),
            LOGIN_THROTTLE_DETAIL,
            now=now,
        )

    async def record_login_failure(self, client_ip: str, email: str):
        now = _utcnow()
        await self._record_failure(
            LOGIN_IP_KEY,
            client_ip,
            self._login_ip_policy(),
            now=now,
        )
        await self._record_failure(
            LOGIN_EMAIL_IP_KEY,
            _login_email_ip_key(email, client_ip),
            self._login_email_ip_policy(),
            now=now,
        )

    async def reset_login_failure_state(self, client_ip: str, email: str):
        await crud.delete_auth_throttle_entry(
            LOGIN_EMAIL_IP_KEY,
            _login_email_ip_key(email, client_ip),
        )

    async def consume_register_attempt(self, client_ip: str):
        await self._assert_key_allowed(
            REGISTER_IP_KEY,
            client_ip,
            self._register_ip_policy(),
            REGISTER_THROTTLE_DETAIL,
            now=_utcnow(),
        )
        await self.record_register_attempt(client_ip)

    async def record_register_attempt(self, client_ip: str):
        await self._consume_attempt(
            REGISTER_IP_KEY,
            client_ip,
            self._register_ip_policy(),
        )

    async def _assert_key_allowed(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        policy: ThrottlePolicy,
        detail: str,
        *,
        now: datetime,
    ):
        entry = await crud.get_auth_throttle_entry(
            throttle_key_type,
            throttle_key_value,
        )
        if not entry:
            return

        locked_until = entry.get("locked_until")
        if locked_until and locked_until > now:
            raise HTTPException(
                status_code=429,
                detail=detail,
                headers={"Retry-After": str(_retry_after_seconds(locked_until, now))},
            )

    async def _consume_attempt(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        policy: ThrottlePolicy,
    ):
        now = _utcnow()
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                entry = await crud.get_auth_throttle_entry(
                    throttle_key_type,
                    throttle_key_value,
                    connection=connection,
                    for_update=True,
                )
                updated_state = self._next_failure_state(
                    entry=entry,
                    policy=policy,
                    now=now,
                )
                await self._persist_state(
                    throttle_key_type,
                    throttle_key_value,
                    updated_state,
                    connection=connection,
                )

    async def _record_failure(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        policy: ThrottlePolicy,
        *,
        now: datetime,
    ):
        async with db.pool.acquire() as connection:
            async with connection.transaction():
                entry = await crud.get_auth_throttle_entry(
                    throttle_key_type,
                    throttle_key_value,
                    connection=connection,
                    for_update=True,
                )
                updated_state = self._next_failure_state(
                    entry=entry,
                    policy=policy,
                    now=now,
                )
                await self._persist_state(
                    throttle_key_type,
                    throttle_key_value,
                    updated_state,
                    connection=connection,
                )

    @staticmethod
    def _next_failure_state(
        *,
        entry: dict | None,
        policy: ThrottlePolicy,
        now: datetime,
    ) -> dict[str, datetime | int | None]:
        if not entry:
            attempt_count = 1
            window_started_at = now
        else:
            window_started_at = entry["window_started_at"]
            if window_started_at + policy.window <= now:
                attempt_count = 1
                window_started_at = now
            else:
                attempt_count = int(entry["attempt_count"]) + 1

        locked_until = None
        if attempt_count >= policy.limit:
            locked_until = now + policy.lockout

        return {
            "attempt_count": attempt_count,
            "window_started_at": window_started_at,
            "last_attempt_at": now,
            "locked_until": locked_until,
        }

    async def _persist_state(
        self,
        throttle_key_type: str,
        throttle_key_value: str,
        state: dict[str, datetime | int | None],
        *,
        connection,
    ):
        entry = await crud.get_auth_throttle_entry(
            throttle_key_type,
            throttle_key_value,
            connection=connection,
            for_update=True,
        )
        if entry:
            await crud.update_auth_throttle_entry(
                int(entry["id"]),
                int(state["attempt_count"]),
                state["window_started_at"],
                state["last_attempt_at"],
                state["locked_until"],
                connection=connection,
            )
            return

        await crud.create_auth_throttle_entry(
            throttle_key_type,
            throttle_key_value,
            int(state["attempt_count"]),
            state["window_started_at"],
            state["last_attempt_at"],
            state["locked_until"],
            connection=connection,
        )


auth_throttle_service = AuthThrottleService()
