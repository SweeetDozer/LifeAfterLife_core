from fastapi import APIRouter, HTTPException

from app.core.security import (
    create_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.db.crud import crud
from app.models.user import UserCreate, UserLogin

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(user: UserCreate):
    existing = await crud.get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="User exists")

    user_id = await crud.create_user(user.email, hash_password(user.password))
    return {"user_id": user_id}


@router.post("/login")
async def login(user: UserLogin):
    db_user = await crud.get_user_by_email(user.email)

    if not db_user or not verify_password(user.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if password_needs_rehash(db_user["password_hash"]):
        await crud.update_user_password_hash(db_user["id"], hash_password(user.password))

    token = create_token(db_user["id"])
    return {"access_token": token, "token_type": "bearer"}
