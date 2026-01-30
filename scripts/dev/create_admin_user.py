import asyncio

import bcrypt
from tortoise import Tortoise

from app.admin.models import AdminUser
from app.core.config import settings
from app.core.tortoise_config import TORTOISE_ORM


async def main() -> None:
    await Tortoise.init(config=TORTOISE_ORM)

    username = settings.ADMIN_USERNAME
    password = settings.ADMIN_PASSWORD

    if not username or not password:
        raise RuntimeError("ADMIN_USERNAME/ADMIN_PASSWORD 환경변수 없음.")

    existing = await AdminUser.get_or_none(username=username)
    hashed_password = bcrypt.hashpw(password.encode("utf8"), bcrypt.gensalt()).decode()

    if existing:
        updated_fields: list[str] = []

        existing_hash = existing.hash_password or ""
        needs_password_update = False

        if not existing_hash:
            needs_password_update = True
        else:
            try:
                needs_password_update = not bcrypt.checkpw(
                    password.encode("utf8"), existing_hash.encode("utf8")
                )
            except ValueError:
                needs_password_update = True

        if needs_password_update:
            existing.hash_password = hashed_password
            updated_fields.append("hash_password")

        if not existing.is_active:
            existing.is_active = True
            updated_fields.append("is_active")

        if not existing.is_superuser:
            existing.is_superuser = True
            updated_fields.append("is_superuser")

        if updated_fields:
            await existing.save(update_fields=updated_fields)
            print(f"[{settings.MODE}] 어드민 유저 갱신 완료: {username}")
        else:
            print(f"[{settings.MODE}] 어드민 유저 이미 존재: {username}")
    else:
        await AdminUser.create(
            username=username,
            hash_password=hashed_password,
            is_superuser=True,
            is_active=True,
        )
        print(f"[{settings.MODE}] 어드민 유저 생성 완료: {username}")

    await Tortoise.close_connections()


if __name__ == "__main__":
    asyncio.run(main())
