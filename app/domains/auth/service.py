from io import BytesIO

import httpx
from fastapi import Response

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token, verify_cognito_token
from app.core.utils.image_resizer import ImageResizer
from app.domains.auth.schemas import TokenResponse
from app.domains.notifications.models import UserNoti
from app.domains.users.models import ProviderChoice, User
from app.integrations.naver import naver_client


class AuthService:
    def __init__(self) -> None:
        self.image_resizer = ImageResizer()

    async def _process_and_upload_image(self, user: User, image_url: str) -> str:
        """
        프로필 URL을 다운로드하여 리사이징 후 S3에 업로드합니다.
        """
        if not image_url:
            return ""

        try:
            async with httpx.AsyncClient() as client:
                img_res = await client.get(image_url)
                if img_res.status_code != 200:
                    return image_url  # 실패 시 원본 유지

                # 메모리에 이미지 로드
                image_data = BytesIO(img_res.content)

                # UserService와 동일한 경로 및 사이즈 설정
                path_prefix = f"users/{user.id}/profile"
                sizes = (100, 300, 640)

                # 리사이징 및 업로드
                urls = await self.image_resizer.upload_square_resizes(
                    image_file=image_data, sizes=sizes, path_prefix=path_prefix
                )

                # 중간 사이즈(300px)를 기본 URL로 반환
                return urls.get("300", image_url)
        except Exception:
            return image_url

    async def process_cognito_login(self, code: str) -> TokenResponse:
        # Cognito Token Endpoint로 code를 보내 토큰들을 가져옴
        async with httpx.AsyncClient() as client:
            token_url = f"{settings.COGNITO_DOMAIN}/oauth2/token"
            data = {
                "grant_type": "authorization_code",
                "client_id": settings.COGNITO_CLIENT_ID,
                "client_secret": settings.COGNITO_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.COGNITO_REDIRECT_URI,
            }
            res = await client.post(token_url, data=data)
            tokens = res.json()

        id_token = tokens.get("id_token")

        # 토큰 검증
        payload = await verify_cognito_token(id_token)

        # payload에서 발급자(iss)를 확인하여 제공자 판별. 대소문자 구분 쉬우라고 소문자처리
        iss = payload.get("iss", "")
        if "kakao" in iss.lower():
            current_provider = ProviderChoice.KAKAO
        elif "google" in iss.lower():
            current_provider = ProviderChoice.GOOGLE
        else:
            current_provider = ProviderChoice.KAKAO

        # Cognito 페이로드에서 정보 추출 (우리 DB 컬럼에 매핑)
        # sub -> provider_id, picture -> profile_img_url
        provider_id = str(payload.get("sub"))

        # 유저 생성 또는 조회 (이미지 처리를 위해 먼저 생성/조회)
        user, created = await User.get_or_create(
            provider_id=provider_id,
            defaults={
                "provider": current_provider,
                "email": payload.get("email"),
                "nickname": payload.get("nickname")
                or payload.get("name")
                or f"user_{provider_id[:8]}",
            },
        )

        # 신규 유저이거나 프로필 이미지가 없는 경우 카카오 이미지 S3 처리
        if created or not user.profile_img_url:
            kakao_img_url = payload.get("picture")  # Cognito 매핑된 프로필 이미지
            if kakao_img_url:
                s3_url = await self._process_and_upload_image(user, kakao_img_url)
                user.profile_img_url = s3_url
                await user.save()

        if created:
            await UserNoti.create(user=user)

        return TokenResponse(
            access_token=create_access_token(user.id),
            refresh_token=create_refresh_token(user.id),
            token_type="bearer",
            is_new_user=created,
        )

    async def process_naver_login(self, code: str, state: str = "naver_login") -> TokenResponse:
        """
        네이버 로그인 프로세스: 토큰 획득 -> 프로필 조회 -> DB 저장/업데이트 -> JWT 발급
        state = 네이버 로그인값 필수...
        """
        # 네이버로부터 액세스 토큰 획득
        access_token = await naver_client.get_access_token(code, state)

        # 네이버 유저 정보 획득
        naver_user_info = await naver_client.get_user_info(access_token)

        provider_id = str(naver_user_info.get("id"))  # 네이버의 유니크 ID
        email = naver_user_info.get("email")
        nickname = naver_user_info.get("nickname") or f"naver_{provider_id[:5]}"
        real_name = naver_user_info.get("name")
        profile_image = naver_user_info.get("profile_image")
        phone_number = naver_user_info.get("mobile")
        formatted_gender = str(naver_user_info.get("gender") or "U")

        # 생일 포맷팅 (네이버: birthday="MM-DD", birthyear="YYYY" -> DB: "YYYY-MM-DD")
        birthday = naver_user_info.get("birthday")  # "10-01"
        birthyear = naver_user_info.get("birthyear")  # "1990"
        birth_date = f"{birthyear}-{birthday}" if birthyear and birthday else None

        # 유저 정보 저장
        user, created = await User.update_or_create(
            provider_id=provider_id,
            provider=ProviderChoice.NAVER,
            defaults={
                "email": email,
                "real_name": real_name,
                "nickname": nickname,
                "profile_img_url": profile_image,  # 우선 원본 저장
                "gender": formatted_gender,
                "phone_number": phone_number,
                "birth_date": birth_date,
            },
        )

        # 프로필 이미지 처리 (기존 카카오 방식과 동일하게 S3 업로드)
        if profile_image:
            new_image_url = await self._process_and_upload_image(user, profile_image)
            user.profile_img_url = new_image_url
            await user.save()

        if created:
            await UserNoti.create(user=user)

        # JWT 발급
        return TokenResponse(
            access_token=create_access_token(subject=user.id),
            refresh_token=create_refresh_token(subject=user.id),
            token_type="bearer",
            is_new_user=created,
        )

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
            samesite="none",
            secure=True,
            httponly=True,
        )


auth_service = AuthService()  # alias
