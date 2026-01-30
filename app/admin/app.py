from fastadmin import fastapi_app as admin_app

from app.admin import resources as _resources  # noqa: F401

__all__ = ["admin_app"]
