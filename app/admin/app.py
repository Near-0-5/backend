from pathlib import Path as FSPath
from fastapi import Request, Depends, Path
from fastadmin import fastapi_app as admin_app
from fastadmin.settings import settings
from fastapi.staticfiles import StaticFiles
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.admin import resources as _resources  # noqa: F401

templates = Jinja2Templates(directory=FSPath(__file__).resolve().parent / "templates")

admin_app.mount(
    "/custom-static",
    StaticFiles(directory=FSPath(__file__).resolve().parent / "templates" / "static"),
    name="custom-static",
)

@admin_app.get(
"/sessions/{session_id}/monitor",
    response_class=HTMLResponse,
    summary="실시간 송출 모니터링 페이지",
    description="관리자가 방송 송출 상태를 확인하고 \
    실시간으로 영상을 프리뷰 할 수 있는 HTML 대시보드",
)
async def stream_monitor_page(
    request: Request,
    session_id: int = Path(..., description="모니터링할 콘서트 세션 ID"),
    # current_admin: User = Depends(get_admin_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        "stream_monitor.html",
        {
            "request": request,
            "session_id": session_id,
            "is_admin": True,
        },
    )



settings.ADMIN_SITE_NAME = "NEAR0.5 관리자"
settings.ADMIN_PRIMARY_COLOR = "#333333"
settings.ADMIN_SITE_HEADER_LOGO = f"/{settings.ADMIN_PREFIX}/custom-static/admin_logo.png"
settings.ADMIN_SITE_SIGN_IN_LOGO = f"/{settings.ADMIN_PREFIX}/custom-static/admin_logo_login.png"

__all__ = ["admin_app"]
