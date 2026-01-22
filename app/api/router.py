"""API 라우터 조립 파일.

여기에 넣을 것:
- 각 도메인의 router를 import해서 include_router로 모아두기
- 버저닝(prefix='/api/v1') 같은 공통 prefix 적용

예:
- auth_router: /auth
- users_router: /users, /me
- streams_router: /streams
"""

from fastapi import APIRouter

from app.domains.artists.router import router as artists_router
from app.domains.auth.router import router as auth_router
from app.domains.chat.router_ws import router as chat_router
from app.domains.notifications.router import router as notifications_router
from app.domains.streams.admin.router import router as streams_admin_router
from app.domains.streams.client.router import router as streams_router
from app.domains.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")

# 도메인 라우터 조립
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(artists_router)
api_router.include_router(streams_router)
api_router.include_router(streams_admin_router)
api_router.include_router(chat_router)
api_router.include_router(notifications_router)
