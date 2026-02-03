from pathlib import Path

from fastadmin import fastapi_app as admin_app
from fastadmin.settings import settings
from fastapi.staticfiles import StaticFiles

from app.admin import resources as _resources  # noqa: F401

admin_app.mount(
    "/custom-static",
    StaticFiles(directory=Path(__file__).resolve().parents[2] / "templates" / "static"),
    name="custom-static",
)

settings.ADMIN_SITE_NAME = "NEAR-0.5 관리자"
settings.ADMIN_PRIMARY_COLOR = "#333333"
settings.ADMIN_SITE_HEADER_LOGO = f"/{settings.ADMIN_PREFIX}/custom-static/admin_logo.png"
settings.ADMIN_SITE_SIGN_IN_LOGO = f"/{settings.ADMIN_PREFIX}/custom-static/admin_logo_login.png"

__all__ = ["admin_app"]
