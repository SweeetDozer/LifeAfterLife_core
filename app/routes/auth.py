from fastapi import APIRouter, HTTPException

from app.core.security import (
    AUTHENTICATION_HEADERS,
    DUMMY_PASSWORD_HASH,
    create_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.crud import crud
from app.models.user import (
    UserCreate,
    UserLogin,
    UserLoginResponse,
    UserRegistrationResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
REGISTRATION_RESPONSE = {"detail": "If the account can be created, you can sign in."}


@router.post("/register", response_model=UserRegistrationResponse)
async def register(user: UserCreate):
    password_hash = hash_password(user.password)
    await crud.create_user(user.email, password_hash)
    return UserRegistrationResponse(**REGISTRATION_RESPONSE)


@router.post("/login", response_model=UserLoginResponse)
async def login(user: UserLogin):
    db_user = await crud.get_user_by_email(user.email)
    stored_password_hash = (
        db_user["password_hash"] if db_user else DUMMY_PASSWORD_HASH
    )

    if not db_user or not verify_password(user.password, stored_password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers=AUTHENTICATION_HEADERS,
        )

    if password_needs_rehash(db_user["password_hash"]):
        await crud.update_user_password_hash(db_user["id"], hash_password(user.password))

    token = create_token(db_user["id"])
    return UserLoginResponse(access_token=token, token_type="bearer")
