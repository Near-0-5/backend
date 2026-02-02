from fastapi import APIRouter

from app.domains.artists.router import router as artists_router
from app.domains.auth.router import router as auth_router
from app.domains.chat.router_ws import router as chat_router
from app.domains.concerts.router import router as concert_admin_router
from app.domains.notifications.router import router as notifications_router
from app.domains.streams.admin.ivs_webhook_router import router as streams_status_router
from app.domains.streams.admin.router import router as streams_admin_router
from app.domains.streams.client.router import router as streams_router
from app.domains.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")

# 도메인 라우터 조립
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(artists_router)
api_router.include_router(concert_admin_router)
api_router.include_router(streams_router)
api_router.include_router(streams_status_router)
api_router.include_router(streams_admin_router)
api_router.include_router(chat_router)
api_router.include_router(notifications_router)
