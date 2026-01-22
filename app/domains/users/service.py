from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

import httpx

from app.core.config import settings
from app.domains.users.models import User, UserCatFav, UserDeleteLog

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

    async def withdraw_kakao_user(
        self, user: User, reason: str = "사용자 요청에 의한 탈퇴"
    ) -> None:
        """회원 탈퇴: DB 데이터 삭제 및 카카오 연결 끊기"""
        # 카카오 Unlink API 호출 (Admin Key 또는 Access Token 필요)
        async with httpx.AsyncClient() as client:
            url = "https://kapi.kakao.com/v1/user/unlink"
            headers = {
                "Authorization": f"KakaoAK {settings.KAKAO_ADMIN_KEY}",  # Admin Key 필요
                "Content-Type": "application/x-www-form-urlencoded",
            }
            params = {"target_id_type": "user_id", "target_id": user.provider_id}
            await client.post(url, headers=headers, params=params)

        # 탈퇴 로그 생성 (users_delete_logs)
        await UserDeleteLog.create(
            user_id=user.id,
            email=user.email,
            reason=reason,
            deleted_at=datetime.now(UTC),
            deleted_by="user",
        )

        # 유저 삭제. 추후 2주 유예기간이 생길 시 수정필요.
        await user.delete()


user_service = UserService()
