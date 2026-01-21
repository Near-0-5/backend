from datetime import date

import pytest

from app.domains.artists.models import Artist
from app.domains.notifications.models import UserNoti
from app.domains.streams.models import CategoryType
from app.domains.users.models import GenderChoices, ProviderChoice, User, UserCatFav
from app.domains.users.service import user_service


@pytest.mark.asyncio
async def test_get_user_profile_success(initialize_tests):
    # 1. 테스트 유저 생성
    user = await User.create(
        provider=ProviderChoice.KAKAO,
        provider_id="kakao_12345",
        email="test@example.com",
        nickname="test_nick",
        real_name="김테스트",
        profile_img_url="http://example.com/profile.jpg",
        bio="안녕하세요!",
        gender=GenderChoices.M,
        birth_date=date(1995, 1, 1),
    )

    # 2. 알림 설정 생성 (UserNoti 모델의 필드명은 위 서비스 코드 로직에 맞춤)
    # 서비스에서 artist_noti, live_noti, marketing_noti를 참조하므로 해당 필드명 사용
    await UserNoti.create(user=user, artist_noti=False, live_noti=True, marketing_noti=True)

    # 3. 팔로우 아티스트 생성 및 관계 추가
    artist = await Artist.create(
        stage_name="뉴진스", profile_img_url="http://example.com/artist.jpg"
    )
    await user.followed_artists.add(artist)

    # 4. 선호 카테고리 추가 (CategoryType Enum 사용)
    # CategoryType에 KPOP, DANCE 등의 값이 있다고 가정합니다.
    await UserCatFav.create(user=user, category=CategoryType.KPOP)
    await UserCatFav.create(user=user, category=CategoryType.BAND)

    # 5. 서비스 메서드 호출
    profile = await user_service.get_user_profile(user.id)

    # 6. 검증
    assert profile["id"] == user.id
    assert profile["nickname"] == "test_nick"
    assert profile["email"] == "test@example.com"
    assert profile["name"] == "김테스트"

    # 아티스트 데이터 검증
    assert len(profile["favorite_artists"]) == 1
    assert profile["favorite_artists"][0]["name"] == "뉴진스"

    # 카테고리 Enum 값 검증 (.value)
    assert CategoryType.KPOP.value in profile["preferred_categories"]
    assert CategoryType.BAND.value in profile["preferred_categories"]

    # 알림 설정 검증
    notis = profile["notification_settings"]
    assert notis["new_content_from_favorite_artists"] is False
    assert notis["live_start_notification"] is True
    assert notis["marketing_consent"] is True


@pytest.mark.asyncio
async def test_get_user_profile_no_relation_data(initialize_tests):
    """관계 데이터(알림, 아티스트, 카테고리)가 전혀 없는 경우의 기본 동작 검증"""
    user = await User.create(
        provider=ProviderChoice.GOOGLE, provider_id="google_999", nickname="pure_user"
    )

    profile = await user_service.get_user_profile(user.id)

    assert profile["favorite_artists"] == []
    assert profile["preferred_categories"] == []

    # 서비스 로직 내의 default 처리 검증
    notis = profile["notification_settings"]
    assert notis["new_content_from_favorite_artists"] is True
    assert notis["live_start_notification"] is True
    assert notis["marketing_consent"] is False
