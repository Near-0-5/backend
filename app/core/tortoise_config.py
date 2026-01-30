from app.core.config import settings

TORTOISE_ORM = {
    "connections": {
        "default": settings.DATABASE_URL,
    },
    "apps": {
        "models": {
            "models": [
                "app.admin.models",
                "app.domains.users.models",
                "app.domains.artists.models",
                "app.domains.streams.models",
                "app.domains.notifications.models",
                "aerich.models",
            ],
            "default_connection": "default",
        }
    },
    "use_tz": True,
    "timezone": "Asia/Seoul",
}
