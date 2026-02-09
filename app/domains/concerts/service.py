from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.core.pagination import paginate_cursor
from app.core.utils.image_resizer import ImageResizer
from app.core.utils.permissions import AdminPermission
from app.domains.concerts.models import Concert
from app.domains.concerts.schemas import (
    ConcertCreateRequest,
    ConcertDetailResponse,
)
from app.domains.users.models import User
from app.integrations.aws_ivs import IVSClient
from app.integrations.aws_ivs.client import logger


class ConcertAdminService:
    def __init__(self, ivs_client: IVSClient):
        self.ivs_client = ivs_client
        self.image_resizer = ImageResizer()

    async def create_concert(self, data: ConcertCreateRequest, user: User) -> Concert:
        """
        [Admin] 콘서트 생성
        """
        AdminPermission.must_be_admin(user)
        return await Concert.create(**data.model_dump())

    def _get_full_image_url(self, path: str | None) -> str:
        """
        DB에 저장된 경로를 확인하여 전체 URL을 반환합니다.
        이미 https://로 시작하면 그대로 반환하고, 아니면 CloudFront 도메인을 붙입니다.
        """
        if not path:
            return ""

        # 이미 전체 URL(https://)이 저장되어 있는 경우 그대로 반환
        if path.startswith("https://"):
            return path

        # 상대 경로인 경우 CloudFront 도메인 결합
        base_url = settings.CLOUDFRONT_DOMAIN.rstrip("/")
        clean_path = path.lstrip("/")
        return f"{base_url}/{clean_path}"

    async def update_concert_thumbnail(
        self, concert_id: int, file: UploadFile, user: User
    ) -> Concert:
        """
        콘서트 썸네일 생성 및 수정
        """
        AdminPermission.must_be_admin(user)

        # 콘서트 있는지 확인
        concert = await Concert.get_or_none(id=concert_id)
        if not concert:
            raise HTTPException(status_code=404, detail="콘서트를 찾을 수 없습니다.")

        # 기존 이미지가 있다면 S3 폴더 삭제
        if concert.thumbnail_url:
            await self.image_resizer.delete_all_by_id_path(concert.thumbnail_url)

        # 새로운 이미지 리사이징 업로드
        path_prefix = f"concerts/{concert.id}/thumbnail"
        sizes = (300, 640, 1280)

        urls = await self.image_resizer.upload_square_resizes(
            image_file=file.file, sizes=sizes, path_prefix=path_prefix
        )

        # DB 업데이트
        img_url = urls.get("640", "")
        pure_path = urlparse(img_url).path.lstrip("/")
        db_path = f"/images/{pure_path}"

        full_url = self._get_full_image_url(db_path)
        concert.thumbnail_url = full_url
        await concert.save()

        return concert

    async def list_concerts(
        self, user: User, limit: int = 20, cursor: int | None = None
    ) -> tuple[list[Concert], int | None]:
        """
        콘서트 목록 조회
        """
        AdminPermission.must_be_admin(user)

        queryset = Concert.all()
        result: Any = await paginate_cursor(queryset, limit=limit, cursor=cursor, order_by="-id")

        concerts: list[Concert] = result[0]
        next_cursor: int | None = result[1]

        return concerts, next_cursor

    async def get_concert_detail(self, concert_id: int, user: User) -> ConcertDetailResponse:
        """
        콘서트 상세 조회(하위 세션 목록 포함)
        """
        AdminPermission.must_be_admin(user)

        concert = await Concert.get_or_none(id=concert_id).prefetch_related(
            "sessions__stream_channel"
        )

        if not concert:
            raise HTTPException(404, "존재하지 않는 콘서트입니다.")

        return ConcertDetailResponse.model_validate(concert)

    async def update_concert(
        self, concert_id: int, data: ConcertCreateRequest, user: User
    ) -> Concert:
        """
        콘서트 수정
        """
        AdminPermission.must_be_admin(user)

        concert = await Concert.get_or_none(id=concert_id)
        if not concert:
            raise HTTPException(404, "수정할 콘서트를 찾을 수 없습니다.")

        # 요청 데이터 반영 (exclude_unset=True로 보낸 값만 수정)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(concert, key, value)

        await concert.save()
        return concert

    async def delete_concert_with_infrastructure(self, concert_id: int, user: User) -> None:
        """
        콘서트 삭제 및 AWS IVS 채널 삭제
        """
        AdminPermission.must_be_admin(user)

        # 세션, 채널 정보 모두 가져옴
        concert = await Concert.get_or_none(id=concert_id).prefetch_related(
            "sessions__stream_channel"
        )

        if not concert:
            raise HTTPException(404, "삭제할 콘서트를 찾을 수 없습니다.")

        # 연결된 모든 세션의 AWS IVS 채널 먼저 삭제
        for session in list(concert.sessions):  # type: ignore[call-overload]
            if hasattr(session, "stream_channel") and session.stream_channel:
                try:
                    self.ivs_client.delete_channel(session.stream_channel.channel_arn)
                except Exception as e:
                    logger.warning(f"콘서트 삭제 중 세션({session.id})의 IVS 채널 삭제 실패: {e}")

        # 썸네일 삭제 (S3)
        if concert.thumbnail_url:
            await self.image_resizer.delete_all_by_id_path(concert.thumbnail_url)

        # DB 삭제(cascade)
        await concert.delete()
