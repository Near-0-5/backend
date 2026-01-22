from datetime import date

from tortoise import Tortoise, run_async

from app.core.config import settings
from app.core.tortoise_config import TORTOISE_ORM
from app.domains.artists.models import Artist, GroupType


async def seed_artists() -> None:
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()

    artists_data = [
        {
            "id": 1,
            "stage_name": "킹율회장",
            "agency": "백",
            "description": "초코 싫어한다면서 맨날 먹음",
            "group_type": GroupType.SOLO,
            "member_count": 1,
            "debut_date": date(2026, 1, 1),
        },
        {
            "id": 2,
            "stage_name": "머용코치",
            "agency": "백",
            "description": "머머머머대머머",
            "group_type": GroupType.BOY_BAND,
            "member_count": 3,
            "debut_date": date(2026, 1, 1),
        },
        {
            "id": 3,
            "stage_name": "BJ준",
            "agency": "프",
            "description": "버튜버 지망생",
            "group_type": GroupType.GIRL_GROUP,
            "member_count": 4,
            "debut_date": date(2026, 6, 1),
        },
    ]

    for artist in artists_data:
        await Artist.get_or_create(id=artist["id"], defaults=artist)

    print(f"[{settings.MODE}] 아티스트 생성 완료")
    await Tortoise.close_connections()


if __name__ == "__main__":
    run_async(seed_artists())
