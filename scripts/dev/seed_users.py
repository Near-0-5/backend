import asyncio

from tortoise import Tortoise

from app.core.config import settings
from app.core.tortoise_config import TORTOISE_ORM
from app.domains.users.models import ProviderChoice, User


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    await User.get_or_create(
        id=1,
        defaults={
            "provider": ProviderChoice.KAKAO,
            "provider_id": "test_admin",
            "nickname": "admin",
            "is_superuser": True,
        },
    )

    await User.get_or_create(
        id=2,
        defaults={
            "provider": ProviderChoice.KAKAO,
            "provider_id": "test_user",
            "nickname": "user",
            "is_superuser": False,
        },
    )

    await Tortoise.close_connections()

    print(f"[{settings.MODE}] 개발용 유저 생성 완료")


if __name__ == "__main__":
    asyncio.run(main())
