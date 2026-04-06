from fastapi import APIRouter, HTTPException
from app.models.user import UserCreate, UserLogin
from app.db.crud import crud
from app.core.security import create_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
async def register(user: UserCreate):
    existing = await crud.get_user_by_email(user.email)
    if existing:
        raise HTTPException(status_code=400, detail="User exists")

    user_id = await crud.create_user(user.email, user.password)
    return {"user_id": user_id}

@router.post("/login")
async def login(user: UserLogin):
    db_user = await crud.get_user_by_email(user.email)

    if not db_user or db_user["password_hash"] != user.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(db_user["id"])
    return {"access_token": token}