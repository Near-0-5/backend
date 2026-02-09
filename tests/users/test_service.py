import io
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from PIL import Image

from app.domains.artists.models import Artist
from app.domains.concerts.models import CategoryType
from app.domains.notifications.models import UserNoti
from app.domains.users.models import GenderChoices, ProviderChoice, User, UserCatFav, UserDeleteLog
from app.domains.users.schemas import NotiSettings, UserMeUpdate
from app.domains.users.service import user_service
from app.integrations.s3_client import S3Client


@pytest.mark.asyncio
async def test_get_user_profile_success(initialize_tests):
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
    await UserNoti.create(user=user, artist_noti=False, live_noti=True, marketing_noti=True)

    artist = await Artist.create(
        stage_name="뉴진스", profile_img_url="http://example.com/artist.jpg"
    )
    await user.followed_artists.add(artist)

    await UserCatFav.create(user=user, category=CategoryType.KPOP)

    profile = await user_service.get_user_profile(user.id)

    assert profile.id == user.id
    assert profile.nickname == "test_nick"
    assert len(profile.favorite_artists) == 1
    assert CategoryType.KPOP.value in profile.preferred_categories
    assert profile.notification_settings.live_start_notification is True


@pytest.mark.asyncio
async def test_get_user_profile_no_relation_data(initialize_tests):
    user = await User.create(
        provider=ProviderChoice.GOOGLE, provider_id="google_999", nickname="pure_user"
    )
    profile = await user_service.get_user_profile(user.id)

    assert profile.favorite_artists == []
    assert profile.preferred_categories == []
    assert profile.notification_settings.live_start_notification is True


@pytest.mark.asyncio
async def test_image_resizer_and_s3_error_cases(initialize_tests):
    user = await User.create(nickname="img_err", provider=ProviderChoice.KAKAO, provider_id="p789")

    invalid_file = MagicMock()
    invalid_file.file = b"not_an_image"

    with pytest.raises(HTTPException):
        await user_service.update_profile_image(user, invalid_file)

    with patch("aioboto3.Session.client") as mock_client:
        mock_s3 = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_s3

        s3 = S3Client()
        await s3.delete_prefix("users/1/profile")
        assert mock_client.called


@pytest.mark.asyncio
async def test_update_profile_image_coverage(initialize_tests):
    user = await User.create(nickname="img_test", provider=ProviderChoice.KAKAO, provider_id="p123")

    img = Image.new("RGB", (10, 10), color="red")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    mock_file = MagicMock()
    mock_file.file = img_byte_arr
    mock_file.filename = "test.png"
    mock_file.content_type = "image/png"

    with (
        patch(
            "app.core.utils.image_resizer.ImageResizer.upload_square_resizes",
            new_callable=AsyncMock,
        ) as mock_upload,
    ):
        # 1. ImageResizer가 반환하는 가상의 S3 Full URL 설정
        mock_upload.return_value = {
            "300": "https://near-images.s3.ap-northeast-2.amazonaws.com/users/1/profile/image_300.png"
        }

        # 2. 서비스 함수 호출
        await user_service.update_profile_image(user, mock_file)

        # 3. DB 확인
        await user.refresh_from_db()

        # [검증 포인트] DB에는 도메인이 제거되고 /images/ 프리픽스가 붙은 경로가 저장되어야 함
        assert user.profile_img_url == "/images/users/1/profile/image_300.png"


@pytest.mark.asyncio
async def test_withdraw_kakao_user_full_flow(initialize_tests):
    user = await User.create(
        provider_id="999",
        provider=ProviderChoice.KAKAO,
        nickname="del_me",
        email="test@example.com",
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        await user_service.withdraw_user(user, reason="테스트 탈퇴")

    assert await User.get_or_none(id=user.id) is None
    assert await UserDeleteLog.filter(email="test@example.com").exists() is True


@pytest.mark.asyncio
async def test_update_user_profile_full(initialize_tests):
    user = await User.create(nickname="old_nick", provider=ProviderChoice.KAKAO, provider_id="p123")
    now = datetime.now()

    update_data = UserMeUpdate(
        nickname="new_nick",
        bio="Hello New Bio",
        updated_at=now,
        notification_settings=NotiSettings(
            new_content_from_favorite_artists=False,
            live_start_notification=False,
            marketing_consent=True,
        ),
    )

    response = await user_service.update_user_profile(user, update_data)
    assert response.nickname == "new_nick"

    await User.create(nickname="other", provider=ProviderChoice.KAKAO, provider_id="p456")
    with pytest.raises(HTTPException) as exc:
        await user_service.update_user_profile(user, UserMeUpdate(nickname="other", updated_at=now))
    assert exc.value.status_code == 409


# --- S3Client 및 ImageResizer 집중 커버리지 테스트 ---


@pytest.mark.asyncio
async def test_s3_client_all_methods_coverage():
    """S3Client의 upload 메서드 호출 시 내부 upload_fileobj가 실행되는지 검증"""
    client = S3Client()
    mock_s3 = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client.return_value = mock_cm

    with patch.object(client, "session", mock_session):
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_file.content_type = "image/jpeg"

        await client.upload(mock_file, path_prefix="test_path")

        # S3Client.upload는 put_object가 아닌 upload_fileobj를 호출함
        assert mock_s3.upload_fileobj.called


@pytest.mark.asyncio
async def test_image_resizer_delete_logic_coverage():
    """ImageResizer가 S3Client의 delete_prefix를 올바른 인자와 함께 호출하는지 테스트"""
    from app.core.utils.image_resizer import ImageResizer

    mock_s3_client = AsyncMock()
    resizer = ImageResizer(s3_client=mock_s3_client)

    valid_url = "https://bucket.s3.region.amazonaws.com/users/123/profile/image_300.png"
    await resizer.delete_all_by_id_path(valid_url)

    mock_s3_client.delete_prefix.assert_called_with(prefix="users/123/profile")


@pytest.mark.asyncio
async def test_s3_client_methods_full_coverage():
    """S3Client의 다양한 메서드 및 ClientError 발생 상황 검증"""
    client = S3Client()
    mock_s3 = AsyncMock()

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client.return_value = mock_cm

    with patch.object(client, "session", mock_session):
        # 1. upload_with_key 성공 테스트 (put_object 호출 확인)
        await client.upload_with_key(b"data", "path.png")
        assert mock_s3.put_object.called

        # 2. delete_prefix 테스트
        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "k1"}]}
        await client.delete_prefix("prefix/")
        assert mock_s3.delete_objects.called

        # 3. ClientError 발생 테스트 (S3Client.upload 내부의 에러 전파 확인)
        # upload 메서드는 upload_fileobj를 호출하므로 여기에 side_effect 설정
        mock_s3.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Upload Error"}}, "UploadFileObj"
        )

        mock_file = MagicMock()
        mock_file.name = "test.png"

        with pytest.raises(ClientError):
            await client.upload(mock_file, path_prefix="test_path")

        # 4. Presigned URL 에러 케이스
        error_msg = "S3 Presign Error"
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": error_msg}}, "generate_presigned_url"
        )
        url = await client.generate_presigned_url("test_key")
        assert error_msg in url


@pytest.mark.asyncio
async def test_s3_generate_presigned_url_error():
    """S3Client.generate_presigned_url의 독립적인 에러 핸들링 테스트"""
    with patch("aioboto3.Session") as mock_session_class:
        mock_s3 = AsyncMock()
        mock_session_instance = MagicMock()
        mock_session_class.return_value = mock_session_instance
        mock_session_instance.client.return_value.__aenter__.return_value = mock_s3

        client = S3Client()
        error_msg = "S3 Presign Error"
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": error_msg}}, "generate_presigned_url"
        )

        url = await client.generate_presigned_url("test_key")
        assert error_msg in url
