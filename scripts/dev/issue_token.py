import asyncio
import sys
from datetime import timedelta

from tortoise import Tortoise

from app.core.security import create_access_token
from app.core.tortoise_config import TORTOISE_ORM
from app.domains.users.models import User
from app.core.security import create_refresh_token


async def main() -> None:
    if len(sys.argv) < 2:
        print("그거 아님 ㅋㅋ")
        print("사용법: uv run python scripts/dev/issue_token.py <user_id>")
        sys.exit(1)

    user_id = int(sys.argv[1])

    await Tortoise.init(config=TORTOISE_ORM)

    user = await User.get_or_none(id=user_id)
    if not user:
        raise RuntimeError(f"admin(1), user(2) | 입력값: {user_id}")

    access_token = create_access_token(
        subject=user.id,
        expires_delta=timedelta(
            days=18
        ),  # 발표까지 남은 기간 (귀찮으니까 토큰 발급해서 가지고 있으셈)
    )

    refresh_token = create_refresh_token(subject=user.id)

    await Tortoise.close_connections()

    print("="*30)
    print(f"      토큰 발급 [ID: {user_id}]")
    print("="*30)
    print("\n[access token]")
    print(access_token)
    print("\n\n[refresh token]")
    print(refresh_token)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"[틀림!!] \n{e}")
        sys.exit(1)
