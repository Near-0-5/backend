from fastapi import FastAPI
from app.core.config import settings


app = FastAPI()

@app.get("/")
def hollw_world():
    if not settings.DB_HOST:
        return {'success': False}
    return f"success: {settings.DB_HOST}"