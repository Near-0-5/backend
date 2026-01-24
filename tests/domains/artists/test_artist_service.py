import pytest

from app.domains.artists.models import Artist, Follow
from app.domains.artists.service import artist_service
from app.domains.streams.models import CategoryType
from app.domains.users.models import ProviderChoice, User



@pytest.mark.asyncio
class TestArtistService:
    async def test_get_artists_pagination(self, initialize_tests):
        """페이징 처리가 정상적으로 이루어지는지 테스트합니다."""
        # 1. 테스트 데이터 25개 생성
        for i in range(25):
            await Artist.create(id=i + 1, stage_name=f"Artist {i}", category_type=CategoryType.KPOP)

        # 2. 첫 번째 페이지 조회 (20개)
        response = await artist_service.get_artists(page=1, page_size=20)

        assert response.total == 25
        assert len(response.items) == 20
        assert response.page == 1
        assert response.page_size == 20

    async def test_get_artists_search_filter(self, initialize_tests):
        """그룹명 검색 필터링이 정상 작동하는지 테스트합니다."""
        await Artist.create(id=101, stage_name="NewJeans", category_type=CategoryType.KPOP)
        await Artist.create(id=102, stage_name="IVE", category_type=CategoryType.KPOP)

        # 'New' 검색 (부분 일치)
        response = await artist_service.get_artists(page=1, page_size=10, search="New")

        assert response.total == 1
        assert response.items[0].name == "NewJeans"

    async def test_get_artists_sort_by_follower(self, initialize_tests):
        """팔로워 많은 순 정렬이 정상 작동하는지 테스트합니다."""
        # 1. 아티스트 생성
        a1 = await Artist.create(id=201, stage_name="Artist Low")
        a2 = await Artist.create(id=202, stage_name="Artist High")

        # 2. 테스트용 유저 생성
        u1 = await User.create(
            id=1,
            email="u1@test.com",
            nickname="u1",
            provider=ProviderChoice.KAKAO,
            provider_id="kakao_1",
        )
        u2 = await User.create(
            id=2,
            email="u2@test.com",
            nickname="u2",
            provider=ProviderChoice.KAKAO,
            provider_id="kakao_2",
        )

        # 3. 팔로우 관계 생성 (a2에게 2명, a1에게 1명)
        await Follow.create(id=1, user=u1, artist=a1)
        await Follow.create(id=2, user=u1, artist=a2)
        await Follow.create(id=3, user=u2, artist=a2)

        # 4. 정렬 조회 (follower 순)
        response = await artist_service.get_artists(page=1, page_size=10, sort_by="follower")

        # 팔로워가 많은 Artist High가 첫 번째여야 함
        assert response.items[0].name == "Artist High"
        assert response.items[0].follower_count == 2
        assert response.items[1].name == "Artist Low"
        assert response.items[1].follower_count == 1

    async def test_get_artists_sort_by_name(self, initialize_tests):
        """이름 가나다순 정렬이 정상 작동하는지 테스트합니다."""
        await Artist.create(id=301, stage_name="나비")
        await Artist.create(id=302, stage_name="가수")

        response = await artist_service.get_artists(page=1, page_size=10, sort_by="name")

        assert response.items[0].name == "가수"
        assert response.items[1].name == "나비"

    async def test_get_artists_empty_result(self, initialize_tests):
        """데이터가 없을 때 빈 목록을 반환하는지 테스트합니다."""
        response = await artist_service.get_artists(page=1, page_size=10)

        assert response.total == 0
        assert len(response.items) == 0
