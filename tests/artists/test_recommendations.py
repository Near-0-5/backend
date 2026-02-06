from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domains.artists.service import artist_service


# Tortoise QuerySet의 비동기 동작을 흉내 내는 가장 확실한 클래스
class MockQuerySet:
    def __init__(self, items):
        self.items = items

    def __await__(self):
        # await 시점에 즉시 self.items(리스트)를 반환하는 제너레이터
        yield
        return self.items

    def __getattr__(self, name):
        # 어떤 메서드(filter, all, limit 등)를 호출해도 다시 자기 자신(MockQuerySet)을 반환
        return lambda *args, **kwargs: self


@pytest.mark.asyncio
async def test_recommend_cold_start_for_new_user(mocker):
    """신규 유저(Cold Start) 추천 로직 검증"""
    mocker.patch(
        "app.domains.artists.service.redis_client.get", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("app.domains.artists.service.redis_client.setex", new_callable=AsyncMock)

    # 1. Follow.filter().values_list() 모킹
    # values_list는 호출 즉시 await 되므로 AsyncMock이 적합합니다.
    mock_follow_qs = MagicMock()
    mock_follow_qs.values_list = AsyncMock(return_value=[])
    mocker.patch("app.domains.artists.models.Follow.filter", return_value=mock_follow_qs)

    # 2. Artist.all()... 결과물 모킹
    mock_artist = MagicMock()
    mock_artist.id = 1
    mock_artist.stage_name = "New Artist"
    mock_artist.profile_img_url = "http://image.com"
    mock_artist.agency = "New Agency"
    mock_artist.follower_count = 0

    # Artist.all()이 호출되면 MockQuerySet 객체를 반환합니다.
    mocker.patch("app.domains.artists.models.Artist.all", return_value=MockQuerySet([mock_artist]))

    # 실행
    result = await artist_service.get_personalized_recommendations(user_id=1)

    # 검증
    assert len(result) > 0
    assert result[0]["recommendation_reason"] == "최근 데뷔한 핫한 아티스트"


@pytest.mark.asyncio
async def test_recommend_based_on_similar_users_logic(mocker):
    """유사 사용자 기반 추천 로직 검증"""
    mocker.patch(
        "app.domains.artists.service.redis_client.get", new_callable=AsyncMock, return_value=None
    )
    mocker.patch("app.domains.artists.service.redis_client.setex", new_callable=AsyncMock)

    # 1. 내 팔로우 목록 [10] 반환
    mock_follow_qs = MagicMock()
    mock_follow_qs.values_list = AsyncMock(return_value=[10])
    mocker.patch("app.domains.artists.models.Follow.filter", return_value=mock_follow_qs)

    # 2. Artist.raw() 결과 (service.py 132라인: [r.id for r in raw_res])
    mock_raw_res = MagicMock()
    mock_raw_res.id = 20
    mocker.patch(
        "app.domains.artists.models.Artist.raw", new_callable=AsyncMock, return_value=[mock_raw_res]
    )

    # 3. 최종 아티스트 상세 정보 쿼리 모킹
    mock_artist = MagicMock()
    mock_artist.id = 20
    mock_artist.stage_name = "Similar Artist"
    mock_artist.profile_img_url = None
    mock_artist.agency = "Similar Agency"
    mock_artist.follower_count = 5

    # Artist.filter()가 MockQuerySet을 반환하게 하여 await 시 리스트가 나오게 함
    mocker.patch(
        "app.domains.artists.models.Artist.filter", return_value=MockQuerySet([mock_artist])
    )

    # 실행
    result = await artist_service.get_personalized_recommendations(user_id=1)

    # 검증
    assert result[0]["id"] == 20
    assert "유사한 스타일" in result[0]["recommendation_reason"]
