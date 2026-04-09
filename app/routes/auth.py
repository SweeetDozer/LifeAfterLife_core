import hmac
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.security import (
    AUTHENTICATION_HEADERS,
    DUMMY_PASSWORD_HASH,
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    get_current_user_id,
    hash_password,
    parse_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.db.crud import crud
from app.db.database import db
from app.models.user import (
    AuthSessionActionResponse,
    RefreshTokenRequest,
    UserCreate,
    UserLogin,
    UserLoginResponse,
    UserRegistrationResponse,
)
from app.services.auth_throttle_service import auth_throttle_service

router = APIRouter(prefix="/auth", tags=["auth"])
REGISTRATION_RESPONSE = {"detail": "If the account can be created, you can sign in."}
LOGOUT_RESPONSE = {
    "detail": "Refresh session revoked. Existing access tokens remain valid until they expire."
}
LOGOUT_ALL_RESPONSE = {
    "detail": "All refresh sessions revoked. Existing access tokens remain valid until they expire."
}


async def _find_refresh_session(
    refresh_token: str,
    *,
    connection,
    for_update: bool = False,
):
    refresh_lookup = parse_refresh_token(refresh_token)
    stored_refresh_token = await crud.get_refresh_token_by_token_id(
        refresh_lookup.token_id,
        connection=connection,
        for_update=for_update,
    )

    if not stored_refresh_token:
        return None

    if not hmac.compare_digest(
        stored_refresh_token["token_hash"],
        refresh_lookup.token_hash,
    ):
        return None

    return stored_refresh_token


def _get_client_ip(request: Request) -> str:
    client_host = request.client.host if request.client else None
    normalized = (client_host or "unknown").strip()
    return normalized[:255] or "unknown"


@router.post("/register", response_model=UserRegistrationResponse)
async def register(user: UserCreate, request: Request):
    await auth_throttle_service.consume_register_attempt(_get_client_ip(request))
    password_hash = hash_password(user.password)
    await crud.create_user(user.email, password_hash)
    return UserRegistrationResponse(**REGISTRATION_RESPONSE)


@router.post("/login", response_model=UserLoginResponse)
async def login(user: UserLogin, request: Request):
    client_ip = _get_client_ip(request)
    await auth_throttle_service.assert_login_allowed(client_ip, user.email)

    db_user = await crud.get_user_by_email(user.email)
    stored_password_hash = (
        db_user["password_hash"] if db_user else DUMMY_PASSWORD_HASH
    )

    if not db_user or not verify_password(user.password, stored_password_hash):
        await auth_throttle_service.record_login_failure(client_ip, user.email)
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers=AUTHENTICATION_HEADERS,
        )

    await auth_throttle_service.reset_login_failure_state(client_ip, user.email)

    if password_needs_rehash(db_user["password_hash"]):
        await crud.update_user_password_hash(db_user["id"], hash_password(user.password))

    refresh_session = create_refresh_token(db_user["id"])
    await crud.create_refresh_token(
        db_user["id"],
        refresh_session.family_id,
        refresh_session.token_id,
        refresh_session.token_hash,
        refresh_session.expires_at,
    )

    return UserLoginResponse(
        access_token=create_access_token(db_user["id"]),
        refresh_token=refresh_session.token,
        token_type="bearer",
    )


@router.post("/refresh", response_model=UserLoginResponse)
async def refresh_tokens(payload: RefreshTokenRequest):
    try:
        parse_refresh_token(payload.refresh_token)
    except TokenValidationError:
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
            headers=AUTHENTICATION_HEADERS,
        ) from None

    async with db.pool.acquire() as connection:
        async with connection.transaction():
            stored_refresh_token = await _find_refresh_session(
                payload.refresh_token,
                connection=connection,
                for_update=True,
            )

            if not stored_refresh_token:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid refresh token",
                    headers=AUTHENTICATION_HEADERS,
                )

            if stored_refresh_token["revoked_at"] is not None:
                await crud.revoke_refresh_token_family(
                    stored_refresh_token["family_id"],
                    connection=connection,
                )
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token replay detected",
                    headers=AUTHENTICATION_HEADERS,
                )

            if stored_refresh_token["expires_at"] <= datetime.utcnow():
                raise HTTPException(
                    status_code=401,
                    detail="Refresh token expired",
                    headers=AUTHENTICATION_HEADERS,
                )

            user = await crud.get_user_by_id(stored_refresh_token["user_id"])
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid refresh token",
                    headers=AUTHENTICATION_HEADERS,
                )

            refresh_session = create_refresh_token(
                stored_refresh_token["user_id"],
                family_id=stored_refresh_token["family_id"],
            )
            await crud.rotate_refresh_token(
                stored_refresh_token["id"],
                refresh_session.token_id,
                refresh_session.token_hash,
                refresh_session.expires_at,
                connection=connection,
            )

    return UserLoginResponse(
        access_token=create_access_token(stored_refresh_token["user_id"]),
        refresh_token=refresh_session.token,
        token_type="bearer",
    )


@router.post("/logout", response_model=AuthSessionActionResponse)
async def logout(payload: RefreshTokenRequest):
    try:
        parse_refresh_token(payload.refresh_token)
    except TokenValidationError:
        return AuthSessionActionResponse(**LOGOUT_RESPONSE)

    async with db.pool.acquire() as connection:
        async with connection.transaction():
            stored_refresh_token = await _find_refresh_session(
                payload.refresh_token,
                connection=connection,
                for_update=True,
            )
            if stored_refresh_token:
                await crud.revoke_refresh_token_family(
                    stored_refresh_token["family_id"],
                    connection=connection,
                )

    return AuthSessionActionResponse(**LOGOUT_RESPONSE)


@router.post("/logout-all", response_model=AuthSessionActionResponse)
async def logout_all(current_user_id: int = Depends(get_current_user_id)):
    await crud.revoke_all_refresh_tokens_for_user(current_user_id)
    return AuthSessionActionResponse(**LOGOUT_ALL_RESPONSE)


@router.post("/revoke-session", response_model=AuthSessionActionResponse)
async def revoke_session(
    payload: RefreshTokenRequest,
    current_user_id: int = Depends(get_current_user_id),
):
    try:
        parse_refresh_token(payload.refresh_token)
    except TokenValidationError:
        return AuthSessionActionResponse(**LOGOUT_RESPONSE)

    async with db.pool.acquire() as connection:
        async with connection.transaction():
            stored_refresh_token = await _find_refresh_session(
                payload.refresh_token,
                connection=connection,
                for_update=True,
            )
            if (
                stored_refresh_token
                and int(stored_refresh_token["user_id"]) == current_user_id
            ):
                await crud.revoke_refresh_token_family_for_user(
                    current_user_id,
                    stored_refresh_token["family_id"],
                    connection=connection,
                )

    return AuthSessionActionResponse(**LOGOUT_RESPONSE)
