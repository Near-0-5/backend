from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.domains.streams.admin.schemas import ConcertCreateRequest
from app.domains.streams.admin.service import StreamAdminService
from app.domains.streams.deps import get_admin_user
from app.domains.streams.models import CategoryType
from app.main import app


@pytest.fixture
def stream_admin_service():
    # IVS 클라이언트와 플레이백 프로바이더는 모킹 처리
    service = StreamAdminService(MagicMock(), MagicMock())
    service.image_resizer = AsyncMock()
    return service


@pytest.fixture
def mock_user_admin():
    user = MagicMock()
    user.id = 1
    user.is_superuser = True
    return user


@pytest.mark.asyncio
class TestConcertBasicCRUD:
    @pytest.fixture(autouse=True)
    def setup(self, stream_admin_service, mock_user_admin):
        self.service = stream_admin_service
        self.admin = mock_user_admin

    # 콘서트 생성 테스트
    async def test_create_concert(self):
        data = ConcertCreateRequest(title="테스트 콘서트", category=CategoryType.KPOP)

        with patch(
            "app.domains.streams.models.Concert.create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = MagicMock(id=1, title="테스트 콘서트")

            result = await self.service.create_concert(data, self.admin)

            assert result.title == "테스트 콘서트"
            mock_create.assert_called_once()

    # 콘서트 리스트 조회 테스트
    async def test_list_concerts(self):
        mock_concerts = [MagicMock(id=1), MagicMock(id=2)]
        with patch(
            "app.domains.streams.admin.service.paginate_cursor", new_callable=AsyncMock
        ) as mock_paginate:
            mock_paginate.return_value = (mock_concerts, 1)

            concerts, next_cursor = await self.service.list_concerts(self.admin, limit=10)

            assert len(concerts) == 2
            assert next_cursor == 1

    # 콘서트 상세 조회 테스트
    async def test_get_concert_detail_success(self):
        concert_id = 1
        mock_concert = MagicMock(id=concert_id)

        mock_query = MagicMock()
        mock_query.prefetch_related.return_value = AsyncMock(return_value=mock_concert)()

        with patch("app.domains.streams.models.Concert.get_or_none") as mock_get:
            mock_get.return_value = mock_query

            with patch("app.domains.streams.admin.schemas.ConcertDetailResponse.model_validate"):
                await self.service.get_concert_detail(concert_id, self.admin)

                mock_get.assert_called_with(id=concert_id)
                mock_query.prefetch_related.assert_called_with("sessions__stream_channel")

    # 콘서트 수정 테스트
    async def test_update_concert(self):
        concert_id = 1
        update_data = ConcertCreateRequest(title="수정된 제목", category=CategoryType.KPOP)
        mock_concert = MagicMock(id=concert_id, title="원본 제목")
        mock_concert.save = AsyncMock()

        with patch(
            "app.domains.streams.models.Concert.get_or_none", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_concert

            result = await self.service.update_concert(concert_id, update_data, self.admin)

            assert result.title == "수정된 제목"
            mock_concert.save.assert_called_once()

    # 콘서트 삭제 테스트
    async def test_delete_concert(self):
        concert_id = 1
        mock_concert = MagicMock(id=concert_id, thumbnail_url="path/to/img.jpg")
        mock_concert.sessions = []
        mock_concert.delete = AsyncMock()

        mock_query = MagicMock()
        mock_query.prefetch_related.return_value = AsyncMock(return_value=mock_concert)()

        with patch("app.domains.streams.models.Concert.get_or_none") as mock_get:
            mock_get.return_value = mock_query

            await self.service.delete_concert_with_infrastructure(concert_id, self.admin)

            # 이미지 삭제 및 DB 삭제 검증
            self.service.image_resizer.delete_all_by_id_path.assert_called_once_with(
                "path/to/img.jpg"
            )
            mock_concert.delete.assert_called_once()

    @pytest.mark.asyncio
    class TestConcertRouter:
        @pytest.fixture(autouse=True)
        def setup_method(self, mock_user_admin):
            # get_admin_user가 호출될 때 항상 mock_user_admin을 반환하도록 설정
            app.dependency_overrides[get_admin_user] = lambda: mock_user_admin
            yield
            # 테스트 종료 후 오버라이드 제거
            app.dependency_overrides.clear()

        # 목록 조회 테스트 (Header 검증 포함)
        async def test_list_concerts_router(self, client: AsyncClient):
            mock_concert = MagicMock(
                id=1,
                title="Test",
                category=CategoryType.KPOP,
                description="설명",
                thumbnail_url="https://example.com/image.jpg",
            )
            mock_concert.thumbnailUrl = "https://example.com/image.jpg"

            mock_concerts = [mock_concert]  # 내부 속성 접근을 위해 MagicMock 사용

            with patch(
                "app.domains.streams.admin.service.StreamAdminService.list_concerts",
                new_callable=AsyncMock,
            ) as mock_list:
                mock_list.return_value = (mock_concerts, "2")

                response = await client.get("/api/v1/admin/concerts")

                assert response.status_code == 200
                assert response.headers["X-Next-Cursor"] == "2"

        # 썸네일 업로드 테스트
        async def test_update_thumbnail_router(self, client: AsyncClient):
            concert_id = 1
            file_content = b"fake image content"
            files = {"thumbnail_file": ("test.jpg", file_content, "image/jpeg")}

            returned_concert = MagicMock(
                id=concert_id,
                title="Test",
                category=CategoryType.KPOP,
                description="Description",
                thumbnail_url="http://path/to/thumb.jpg",
                thumbnailUrl="http://path/to/thumb.jpg",  # alias 대응
            )

            with patch(
                "app.domains.streams.admin.service.StreamAdminService.update_concert_thumbnail",
                new_callable=AsyncMock,
            ) as mock_thumb:
                mock_thumb.return_value = returned_concert

                response = await client.patch(
                    f"/api/v1/admin/concerts/{concert_id}/thumbnail",
                    files=files,
                )

                assert response.status_code == 200
