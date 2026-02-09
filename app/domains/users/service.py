from datetime import UTC, datetime
from typing import cast
from urllib.parse import urlparse

import boto3
from fastapi import HTTPException, Response, UploadFile, status
from tortoise.transactions import in_transaction

from app.core.config import settings
from app.core.redis import redis_client
from app.core.utils.image_resizer import ImageResizer
from app.domains.artists.models import Artist, Follow
from app.domains.notifications.models import UserNoti
from app.domains.users.models import ProviderChoice, User, UserCatFav, UserDeleteLog
from app.domains.users.schemas import (
    FavoriteArtistCreate,
    FavoriteArtistItem,
    FavoriteArtistListResponse,
    FavoriteArtistResponse,
    UserMeResponse,
    UserMeUpdate,
)


class UserService:
    def __init__(self) -> None:
        self.image_resizer = ImageResizer()

    def _get_full_image_url(self, path: str | None) -> str:
        """
        ArtistService와 동일하게 DB의 상대 경로에 CloudFront 도메인을 결합합니다.
        """
        if not path:
            return ""

        if path.startswith("https://"):
            return path

        base_url = settings.CLOUDFRONT_DOMAIN.rstrip("/")
        clean_path = path.lstrip("/")
        return f"{base_url}/{clean_path}"

    async def get_user_profile(self, user_id: int) -> UserMeResponse:
        """
        사용자의 상세 프로필 정보를 조회합니다.
        (팔로우한 아티스트, 알림 설정, 선호 카테고리 포함)
        """

        # 이미 인증이 완료된 current_user 객체를 바로 사용
        user = await User.get(id=user_id).prefetch_related(
            "followed_artists", "noti_setting", "fav_categories"
        )
        notis = user.noti_setting
        fav_categories = cast("list[UserCatFav]", user.fav_categories)

        return UserMeResponse.from_orm_user_profile_custom(
            user=user, notis=notis, fav_cats=fav_categories
        )

    async def update_user_profile(
        self, user: User, data: UserMeUpdate, profile_file: UploadFile | None = None
    ) -> UserMeResponse:
        """
        내 정보를 수정합니다. (닉네임 중복 체크, 이미지 S3 업로드, 알림 설정 업데이트 포함)
        """
        async with in_transaction():
            # 변경 시의 닉네임 중복 체크
            if data.nickname and data.nickname != user.nickname:
                if await User.filter(nickname=data.nickname).exists():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, detail="이미 사용 중인 닉네임입니다."
                    )
                user.nickname = data.nickname

            # 프로필 이미지 처리
            if profile_file:
                # 기존 프로필 이미지가 S3에 있다면 해당 Prefix 폴더를 통째로 삭제
                # image_url 예: https://bucket.s3.region.amazonaws.com/users/1/profile/image_300.png
                user = await self._update_profile(user, profile_file)

            # 자기소개 업데이트
            if data.bio is not None:
                user.bio = data.bio

            # 알림 설정 업데이트
            if data.notification_settings:
                # get_or_create를 통해 설정이 없을 경우 생성
                noti_settings, _ = await UserNoti.get_or_create(user=user)
                noti_settings.artist_noti = (
                    data.notification_settings.new_content_from_favorite_artists
                )
                noti_settings.live_noti = data.notification_settings.live_start_notification
                noti_settings.marketing_noti = data.notification_settings.marketing_consent
                await noti_settings.save()

            await user.save()
            # 관계 데이터 반영을 위해 다시 로드
            return await self.get_user_profile(user.id)

    async def update_profile_image(self, user: User, file: UploadFile) -> UserMeResponse:
        """
        프로필 이미지만을 업데이트한다.

        1. 기존 프로필 이미지가 있다면 S3에서 해당 폴더 삭제
        2. 새로운 이미지를 리사이징하여 S3 업로드
        3. DB의 profile_img_url 업데이트
        """
        user = await self._update_profile(user, file)
        await user.save()

        return await self.get_user_profile(user.id)

    async def _update_profile(self, user: User, file: UploadFile) -> User:
        """
        내부 중복로직 처리용

        1. 기존 프로필 이미지가 있다면 S3에서 해당 폴더 삭제
        2. 새로운 이미지를 리사이징하여 S3 업로드
        3. DB의 profile_img_url 업데이트
        """
        # 기존 이미지 삭제 (폴더 단위 삭제)
        if user.profile_img_url:
            # image_resizer에 이미 구현된 delete_all_by_id_path 활용
            await self.image_resizer.delete_all_by_id_path(user.profile_img_url)

        # 새 이미지 업로드 (Prefix 설정)
        path_prefix = f"users/{user.id}/profile"
        sizes = (100, 300, 640)

        urls = await self.image_resizer.upload_square_resizes(
            image_file=file.file, sizes=sizes, path_prefix=path_prefix
        )

        # DB 업데이트 (예: 중간 사이즈인 300px을 기본 URL로 저장)
        img_url_300 = urls.get("300")
        if img_url_300:
            pure_path = urlparse(img_url_300).path.lstrip("/")
            user.profile_img_url = f"/images/{pure_path}"
        else:
            user.profile_img_url = ""

        return user

    async def withdraw_user(self, user: User, reason: str = "사용자 요청에 의한 탈퇴") -> None:
        """
        회원 탈퇴: DB 데이터 삭제 및 카카오 연결 끊기
        회원 탈퇴 통합 로직
            - 카카오/구글: Cognito User Pool에서 삭제
            - 네이버: (선택사항) 네이버 연동 해제 API 호출 + DB 삭제
            - S3 프로필 폴더 전체 삭제
            - 탈퇴 로그 생성 및 유저 삭제
        """
        # 카카오 & 구글 (Cognito 사용 그룹)
        if user.provider in [ProviderChoice.KAKAO, ProviderChoice.GOOGLE]:
            # Cognito에서 유저를 삭제해야 다음번 소셜 로그인 시 충돌이 안 납니다.
            client = boto3.client("cognito-idp", region_name=settings.AWS_REGION)
            try:
                # provider_id에 저장된 Cognito의 'sub' 값을 사용하여 삭제
                client.admin_delete_user(
                    UserPoolId=settings.COGNITO_USER_POOL_ID, Username=user.provider_id
                )
            except client.exceptions.UserNotFoundException:
                pass  # 이미 없는 경우 무시
            except Exception as e:
                # 로그 기록 등 처리
                print(f"Cognito 삭제 에러: {e}")
        elif user.provider == ProviderChoice.NAVER:
            """
            네이버는 서버사이드에서 완전한 Unlink를 하려면 
            유저가 로그인 할 때 네이버가 준 Access Token이 필요합니다.
            토큰을 따로 DB에 저장하지 않기에 네이버측 연결 해제는 유저가 직접 하도록 해야합니다.
            네이버는 Admin Key 를 제공하지 않습니다.
            반드시 유저 개개인의 access_token을 사용해야만 연동 해제가 가능합니다.
            레디스는 시간 지나면 탈퇴가 불가능해지고
            세션과 쿠키에 암호화하여 들고있는것은 쿠키 용량이나 보안측면에서 좋지 않아보입니다.
            우선 우리 서비스 DB 삭제만 진행합니다.
            네이버 로그인 버립시다. 여러모로 귀찮게하네 사람.
            """
            pass

        # S3 프로필 이미지 및 폴더 삭제
        # image_resizer가 URL에서 경로를 추출하여 users/{id}/profile 내 모든 파일을 지웁니다.
        if user.profile_img_url:
            await self.image_resizer.delete_all_by_id_path(user.profile_img_url)

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

    async def get_favorite_artists(self, user: User) -> FavoriteArtistListResponse:
        """
        사용자가 팔로우한 아티스트 목록을 조회합니다.
        팔로우한 artists의 정보와 수를 가져옵니다.
        """
        # 최신 팔로우 순으로 정렬
        follow_records = (
            await Follow.filter(user=user).select_related("artist").order_by("-created_at")
        )

        items = [
            FavoriteArtistItem(
                id=record.artist.id,
                name=record.artist.stage_name,
                profile_img_url=self._get_full_image_url(record.artist.profile_img_url),
                category_type=record.artist.category_type,
                group_type=record.artist.group_type,
                member_count=record.artist.member_count,
                agency=record.artist.agency,
                created_at=record.created_at,
            )
            for record in follow_records
        ]

        return FavoriteArtistListResponse(total=len(items), items=items)

    async def add_follow_artist(
        self, user: User, data: FavoriteArtistCreate
    ) -> FavoriteArtistResponse:
        """
        사용자의 선호 아티스트를 추가합니다.
        """
        # 아티스트 존재 여부 확인
        artist = await Artist.get_or_none(id=data.artist_id)
        if not artist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"아티스트(ID: {data.artist_id})를 찾을 수 없습니다.",
            )

        # 중복 팔로우 체크 및 생성 (get_or_create 보다 명시적인 에러 처리를 위해 분리)
        follow, created = await Follow.get_or_create(user=user, artist=artist)
        if not created:
            raise HTTPException(status_code=409, detail="이미 추가된 아티스트입니다.")

        # 추천 아티스트 캐시 삭제
        await redis_client.delete(f"user_recommendation:{user.id}")

        return FavoriteArtistResponse(
            user_id=user.id,
            artist_id=artist.id,
            artist_name=artist.stage_name,  # Artist 모델의 stage_name 사용
            profile_img_url=self._get_full_image_url(
                artist.profile_img_url
            ),  # alias 설정에 따라 매핑
            created_at=follow.created_at,  # Follow 모델의 생성일
        )

    async def remove_follow_artist(self, user: User, artist_id: int) -> Response:
        """
        사용자가 요청한 선호 아티스트를 삭제(언팔로우)합니다.
        """
        # 팔로우 관계 존재 여부 확인
        follow = await Follow.get_or_none(user=user, artist_id=artist_id)

        if not follow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"팔로우 중인 아티스트(ID: {artist_id})를 찾을 수 없습니다.",
            )

        # 팔로우 기록 삭제
        await follow.delete()

        # 추천 아티스트 캐시 삭제
        await redis_client.delete(f"user_recommendation:{user.id}")

        return Response(status_code=status.HTTP_204_NO_CONTENT)


user_service: UserService = UserService()
