from fastapi import FastAPI
from app.core.config import settings


app = FastAPI()

@app.get("/")
def hello_world():
    if not settings.DB_HOST:
        return {"success": False}
    return {"success": True, "db_host": settings.DB_HOST}