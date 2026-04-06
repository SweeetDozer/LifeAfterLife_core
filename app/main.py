from fastapi import FastAPI
from app.db.database import db
from app.routes import auth, graph, kinship, persons, relationships, trees



app = FastAPI()

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

app.include_router(auth.router)
app.include_router(trees.router)
app.include_router(auth.router)
app.include_router(trees.router)
app.include_router(persons.router)
app.include_router(auth.router)
app.include_router(trees.router)
app.include_router(persons.router)
app.include_router(relationships.router)
app.include_router(graph.router)
app.include_router(kinship.router)