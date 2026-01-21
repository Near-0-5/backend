from typing import TYPE_CHECKING, Any, cast

from app.domains.users.models import User, UserCatFav

if TYPE_CHECKING:
    # 런타임에는 필요 없지만 타입 힌트용으로만 쓰이는 임포트
    from collections.abc import Iterable


class UserService:
    async def get_user_profile(self, user_id: int) -> dict[str, Any]:
        """
        사용자의 상세 프로필 정보를 조회합니다.
        (팔로우한 아티스트, 알림 설정, 선호 카테고리 포함)
        """

        # 이미 인증이 완료된 current_user 객체를 바로 사용
        user = await User.get(id=user_id).prefetch_related(
            "followed_artists", "noti_setting", "fav_categories"
        )

        notis = user.noti_setting
        fav_categories = cast("Iterable[UserCatFav]", user.fav_categories)

        return {
            "id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "name": user.real_name,
            "profile_image": user.profile_img_url,
            "joined_at": user.created_at,
            "bio": user.bio,
            "favorite_artists": [
                {
                    "id": artist.id,
                    "name": artist.stage_name,
                    "profile_image": artist.profile_img_url,
                }
                for artist in user.followed_artists
            ],
            "preferred_categories": [cat.category.value for cat in fav_categories],
            "notification_settings": {
                "new_content_from_favorite_artists": notis.artist_noti if notis else True,
                "live_start_notification": notis.live_noti if notis else True,
                "marketing_consent": notis.marketing_noti if notis else False,
            },
        }


user_service = UserService()
