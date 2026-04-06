from fastapi import FastAPI
from app.db.database import db
from app.routes import auth, trees



app = FastAPI()

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

app.include_router(auth.router)
app.include_router(trees.router)