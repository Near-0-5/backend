"""FastAPI 엔트리포인트.

여기에 넣을 것:
- FastAPI() 생성
- lifespan(startup/shutdown)에서 DB init/close
- app.include_router(...)로 도메인 라우터를 조립
- health check 같은 최소 라우트

주의:
- 여기서 비즈니스 로직을 직접 구현하지 말고, domains/* 로 위임하는 패턴으로 가면 유지보수 쉬움.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from tortoise import Tortoise

from app.api.router import api_router
from app.core.tortoise_config import TORTOISE_ORM

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """서버 시작/종료 훅.

    startup(위쪽):
    - Tortoise.init(...)로 DB 연결/모델 등록 준비
    - 필요하면 DB 헬스체크(SELECT 1)
    - 운영에서는 generate_schemas 대신 aerich 마이그레이션 사용 추천

    shutdown(아래쪽):
    - Tortoise.close_connections()로 커넥션 정리
    """
    await Tortoise.init(config=TORTOISE_ORM)
    # TODO: 필요하면 DB 연결 헬스체크를 여기서 수행 (예: SELECT 1)
    yield
    await Tortoise.close_connections()


app = FastAPI(title="NEAR0.5 API", lifespan=lifespan)

# v1 라우터 조립(도메인 라우터는 app/api/router.py에서 관리)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, bool]:
    """기본 헬스체크.

    여기에 넣을 것:
    - 앱이 떠있는지 확인하는 용도(로드밸런서/모니터링)
    - DB까지 확인하고 싶으면 /health/db 같은 엔드포인트를 추가
    """
    return {"ok": True}
