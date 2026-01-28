import pytest
from httpx import AsyncClient

from app.domains.artists.models import Artist
from app.domains.streams.models import CategoryType


@pytest.mark.asyncio
class TestArtistRouter:
    async def test_get_artist_list_router(self, client: AsyncClient, initialize_tests):
        """GET /artists 라우터 엔드포인트를 테스트합니다."""
        # 데이터 준비
        await Artist.create(id=1, stage_name="Router Artist", category_type=CategoryType.KPOP)

        # API 호출
        response = await client.get("/api/v1/artists?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Router Artist"

    async def test_get_artist_detail_router(self, client: AsyncClient, initialize_tests):
        """GET /artists/{artist_id} 라우터 엔드포인트를 테스트합니다."""
        # 데이터 준비
        await Artist.create(
            id=2,
            stage_name="Detail Router",
            agency="Router Agency",
            category_type=CategoryType.KPOP,
        )

        # API 호출
        response = await client.get("/api/v1/artists/2")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 2
        assert data["name"] == "Detail Router"

    async def test_get_artist_detail_not_found_router(self, client: AsyncClient, initialize_tests):
        """라우터를 통한 상세 조회 실패(404)를 테스트합니다."""
        response = await client.get("/api/v1/artists/9999")

        assert response.status_code == 404
        assert response.json()["detail"] == "요청하신 아티스트를 찾을 수 없습니다."
