import uuid
from datetime import datetime

from fastapi import Response

from app.core.security import create_access_token, create_refresh_token
from app.domains.auth.schemas import TokenResponse
from app.domains.notifications.models import UserNoti
from app.domains.users.models import ProviderChoice, User
from app.integrations.kakao import kakao_client


class AuthService:
    async def process_kakao_login(self, code: str) -> TokenResponse:
        # 카카오 토큰 획득
        kakao_access_token = await kakao_client.get_access_token(code)

        # 카카오 사용자 정보 획득
        kakao_user = await kakao_client.get_user_info(kakao_access_token)

        provider_id = str(kakao_user.get("id"))
        kakao_account = kakao_user.get("kakao_account", {})
        profile = kakao_account.get("profile", {})

        # 성별 변환 (male -> M, female -> F)
        raw_gender = kakao_account.get("gender")
        formatted_gender = {"male": "M", "female": "F"}.get(raw_gender)

        # 생년월일 통합 (yyyy-mm-dd -> 카카오 응답: birthyear="1990", birthday="0101")
        birth_date = None
        birth_year = kakao_account.get("birthyear")
        birth_day = kakao_account.get("birthday")

        if birth_year and birth_day:
            try:
                # 1990 + 0101 -> 1990-01-01
                date_str = f"{birth_year}-{birth_day[:2]}-{birth_day[2:]}"
                birth_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                birth_date = None

        # 닉네임이 이미 DB에 있을 경우 닉네임 중복 방지
        nickname = profile.get("nickname", f"user_{provider_id[:5]}")
        existing_user = await User.get_or_none(nickname=nickname)
        if existing_user and existing_user.provider_id != provider_id:
            nickname = f"{nickname}_{uuid.uuid4().hex[:4]}"  # 랜덤 값 삽입

        # DB 저장
        user, created = await User.update_or_create(
            provider_id=provider_id,
            provider=ProviderChoice.KAKAO,
            defaults={
                "email": kakao_account.get("email"),
                "real_name": kakao_account.get("real_name"),
                "nickname": nickname,
                "profile_img_url": profile.get("profile_image_url"),
                "gender": formatted_gender,
                "phone_number": kakao_account.get("phone_number"),  # "010-1234-5678" 등
                "birth_date": birth_date,
            },
        )

        # 유저 생성시 기본 알림 설정
        if created:
            await UserNoti.create(user=user)  # 기본값(True, True, False)으로 생성

        # JWT 토큰 발급
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            is_new_user=created,
        )

    async def refresh_access_token(self, user_id: int) -> TokenResponse:
        """리프레시 토큰을 이용한 액세스 토큰 재발급"""
        # DB에서 유저 존재 확인 등의 추가 검증 가능
        access_token = create_access_token(subject=user_id)
        refresh_token = create_refresh_token(subject=user_id)

        return TokenResponse(
            access_token=access_token, refresh_token=refresh_token, is_new_user=False
        )

    async def logout_user(self, response: Response) -> None:
        """리프레시 토큰 쿠키 삭제"""
        response.delete_cookie(
            key="refresh_token",
            path="/",
        )


auth_service = AuthService()  # alias
