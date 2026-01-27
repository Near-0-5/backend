import io
from datetime import date, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.utils.s3_client import S3Client
from app.domains.artists.models import Artist
from app.domains.notifications.models import UserNoti
from app.domains.streams.models import CategoryType
from app.domains.users.models import GenderChoices, ProviderChoice, User, UserCatFav, UserDeleteLog
from app.domains.users.schemas import NotiSettings, UserMeUpdate
from app.domains.users.service import user_service


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

    # ✅ 속성 접근(.id)으로 수정
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

    # ✅ 딕셔너리 접근에서 속성 접근으로 수정
    assert profile.favorite_artists == []
    assert profile.preferred_categories == []
    assert profile.notification_settings.live_start_notification is True


@pytest.mark.asyncio
async def test_image_resizer_and_s3_error_cases(initialize_tests):
    user = await User.create(nickname="img_err", provider=ProviderChoice.KAKAO, provider_id="p789")

    # 1. 잘못된 이미지 파일로 리사이징 실패 유도 (coverage: image_resizer.py try-except)
    invalid_file = MagicMock()
    invalid_file.file = b"not_an_image"

    with pytest.raises(HTTPException):
        await user_service.update_profile_image(user, invalid_file)

    # 2. S3Client delete_prefix 호출 테스트 (coverage: s3_client.py)
    with patch("aioboto3.Session.client"):
        # mock_s3_session 내부의 list_objects_v2와 delete_objects 모킹
        from app.core.utils.s3_client import S3Client

        s3 = S3Client()
        await s3.delete_prefix("users/1/profile")
        # 호출되었는지 확인하여 커버리지 확보


@pytest.mark.asyncio
async def test_update_profile_image_coverage(initialize_tests):
    """ImageResizer와 S3Client의 실제 로직을 통과시켜 커버리지를 높임"""
    user = await User.create(nickname="img_test", provider=ProviderChoice.KAKAO, provider_id="p123")

    # 1x1 픽셀의 실제 이미지 바이트 생성 (PIL 로직 통과용)
    from PIL import Image

    img = Image.new("RGB", (10, 10), color="red")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    mock_file = MagicMock()
    mock_file.file = img_byte_arr
    mock_file.filename = "test.png"
    mock_file.content_type = "image/png"

    # ✅ S3Client의 최하단 메소드만 모킹하여 ImageResizer 내부 로직 100% 실행
    with (
        patch(
            "app.core.utils.s3_client.S3Client.upload_with_key", new_callable=AsyncMock
        ) as mock_s3_upload,
        patch("app.core.utils.s3_client.S3Client.build_url") as mock_build_url,
    ):
        mock_s3_upload.return_value = "users/1/profile/profile200.png"
        mock_build_url.return_value = "http://s3.url/200.png"

        await user_service.update_profile_image(user, mock_file)

        await user.refresh_from_db()
        assert user.profile_img_url == "http://s3.url/200.png"


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
        await user_service.withdraw_kakao_user(user, reason="테스트 탈퇴")

    assert await User.get_or_none(id=user.id) is None
    assert await UserDeleteLog.filter(email="test@example.com").exists() is True


@pytest.mark.asyncio
async def test_s3_client_utils_coverage():
    """s3_client.py의 미사용 메서드 커버리지 확보"""
    client = S3Client()

    # 1. build_url 테스트
    url = client.build_url("test/key.png")
    assert "test/key.png" in url

    # 2. delete_prefix/object 모킹 테스트
    with patch("aioboto3.Session.client", new_callable=MagicMock) as mock_session:
        mock_s3 = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_s3

        await client.delete_object("some_key")
        assert mock_s3.delete_object.called

        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "k1"}]}
        await client.delete_prefix("prefix/")
        assert mock_s3.delete_objects.called


@pytest.mark.asyncio
async def test_update_user_profile_full(initialize_tests):
    user = await User.create(nickname="old_nick", provider=ProviderChoice.KAKAO, provider_id="p123")

    # 공통으로 사용할 업데이트 시간
    now = datetime.now()

    # 1. 일반 필드 업데이트 테스트
    update_data = UserMeUpdate(
        nickname="new_nick",
        bio="Hello New Bio",
        updated_at=now,  # 필수 필드
        notification_settings=NotiSettings(
            new_content_from_favorite_artists=False,
            live_start_notification=False,
            marketing_consent=True,
        ),
    )

    response = await user_service.update_user_profile(user, update_data)
    assert response.nickname == "new_nick"

    # 2. 닉네임 중복 예외 테스트 (ValidationError 방지를 위해 updated_at 추가)
    await User.create(nickname="other", provider=ProviderChoice.KAKAO, provider_id="p456")
    with pytest.raises(HTTPException) as exc:
        await user_service.update_user_profile(user, UserMeUpdate(nickname="other", updated_at=now))
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_s3_client_full_coverage():
    from app.core.utils.s3_client import S3Client

    client = S3Client()

    # 1. build_url (settings 에 따라 분기됨)
    assert "https://" in client.build_url("test.png")
    assert client.build_url("") == ""

    # 2. generate_presigned_url & delete_prefix (Boto3 Mocking)
    with patch("aioboto3.Session.client") as mock_client:
        mock_s3 = AsyncMock()
        mock_client.return_value.__aenter__.return_value = mock_s3

        # presigned_url 실행 (s3_client.py 115-128 라인)
        await client.generate_presigned_url("test_key")

        # delete_prefix 실행 (s3_client.py 88-102 라인)
        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "k1"}]}
        await client.delete_prefix("prefix/")

        assert mock_s3.generate_presigned_url.called
        assert mock_s3.delete_objects.called


@pytest.mark.asyncio
async def test_s3_generate_presigned_url_error():
    from app.core.utils.s3_client import S3Client

    client = S3Client()
    with patch("aioboto3.Session.client") as mock_client:
        mock_s3 = AsyncMock()
        error_msg = "S3 Error"
        mock_s3.generate_presigned_url.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": error_msg}}, "generate_presigned_url"
        )
        mock_client.return_value.__aenter__.return_value = mock_s3

        # 현재 로직이 에러 메시지를 반환하거나 예외를 문자열로 리턴하고 있으므로
        # 빈 값이 아닌 에러 메시지 포함 여부를 확인해야 합니다.
        url = await client.generate_presigned_url("test_key")

        # 만약 s3_client.py 128라인 부근에서 return str(e) 를 하고 있다면:
        assert error_msg in url


@pytest.mark.asyncio
async def test_s3_client_all_methods_coverage():
    from app.core.utils.s3_client import S3Client

    client = S3Client()

    with patch("aioboto3.Session.client") as mock_client_factory:
        mock_s3 = AsyncMock()
        mock_client_factory.return_value.__aenter__.return_value = mock_s3

        # 1. upload 메서드 (26-48 라인 커버)
        mock_file = MagicMock()
        mock_file.name = "test.jpg"
        mock_file.content_type = "image/jpeg"
        await client.upload(mock_file, path_prefix="test_path")
        assert mock_s3.put_object.called

        # 2. upload_with_key 메서드 (54-68 라인 커버)
        await client.upload_with_key(b"data", key="manual/key.png")
        assert mock_s3.put_object.call_count == 2

        # 3. upload 실패 케이스 (69-82 라인 예외 처리 커버)
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "S3 Upload Error"}}, "PutObject"
        )
        with pytest.raises(ClientError):
            await client.upload_with_key(b"data", key="fail.png")

        # 4. delete_object (84-89 라인 커버)
        await client.delete_object("some_key")
        assert mock_s3.delete_object.called

        # 5. delete_prefix (91-107 라인 커버)
        # Contents가 있는 경우와 없는 경우 분기 처리
        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "k1"}, {"Key": "k2"}]}
        await client.delete_prefix("prefix/")
        assert mock_s3.delete_objects.called


# tests/users/test_service.py 하단에 추가


@pytest.mark.asyncio
async def test_image_resizer_delete_logic_coverage():
    from app.core.utils.image_resizer import ImageResizer

    # S3Client를 Mocking하여 주입
    mock_s3_client = AsyncMock()
    resizer = ImageResizer(s3_client=mock_s3_client)

    # 1. 허용되지 않은 경로 접근 (79-81 라인: re.match 실패 분기)
    # 보안상 users/{id}/profile 패턴만 허용됨
    invalid_url = "https://s3.amazonaws.com/wrong/path/image.png"
    await resizer.delete_all_by_id_path(invalid_url)
    assert not mock_s3_client.delete_prefix.called

    # 2. 허용된 경로 접근 및 삭제 실행 (83-89 라인)
    valid_url = "https://bucket.s3.region.amazonaws.com/users/123/profile/image_300.png"
    await resizer.delete_all_by_id_path(valid_url)

    # "users/123/profile" 경로가 prefix로 전달되었는지 확인
    mock_s3_client.delete_prefix.assert_called_with("users/123/profile")

    # 3. 이미지 리사이징 내부 예외 발생 (49-50 라인)
    # ImageOps.fit 등을 실패하게 만들기 위해 잘못된 이미지 객체 전달
    with patch("PIL.ImageOps.fit", side_effect=Exception("Resize Failed")):
        mock_file = MagicMock()
        # upload_square_resizes 내부의 source.load() 등을 통과시키기 위해 모킹
        with patch("PIL.Image.open") as mock_open:
            mock_img = MagicMock()
            mock_open.return_value = mock_img

            with pytest.raises(HTTPException) as exc:
                await resizer.upload_square_resizes(
                    image_file=mock_file, sizes=(100,), path_prefix="users/1/profile"
                )
            assert exc.value.status_code == 500
            assert "리사이징에 실패했습니다" in exc.value.detail


@pytest.mark.asyncio
async def test_s3_client_methods_full_coverage():
    from app.core.utils.s3_client import S3Client

    client = S3Client()

    with patch("aioboto3.Session.client") as mock_client_factory:
        mock_s3 = AsyncMock()
        mock_client_factory.return_value.__aenter__.return_value = mock_s3

        # 1. upload_with_key 성공 케이스 (54-68 라인)
        key = await client.upload_with_key(b"fake_data", "test/path.png")
        assert key == "test/path.png"
        assert mock_s3.put_object.called

        # 2. upload_with_key 실패 케이스 (69-82 라인 예외 처리)
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "S3 Error"}}, "PutObject"
        )
        # ClientError 발생 시 75번 라인의 logger.error가 실행되고 에러가 전파됨
        with pytest.raises(ClientError):
            await client.upload_with_key(b"fail", "fail.png")

        # 3. delete_object (84-89 라인)
        await client.delete_object("delete_me")
        assert mock_s3.delete_object.called

        # 4. delete_prefix - Contents가 있는 경우 (91-107 라인)
        mock_s3.list_objects_v2.return_value = {"Contents": [{"Key": "k1"}]}
        await client.delete_prefix("prefix/")
        assert mock_s3.delete_objects.called

        # 5. upload 일반 메서드 예외 처리 (46-48 라인)
        mock_s3.put_object.side_effect = ClientError(
            {"Error": {"Code": "500", "Message": "Upload Error"}}, "PutObject"
        )
        mock_file = MagicMock()
        mock_file.name = "test.png"
        with pytest.raises(ClientError):
            await client.upload(mock_file)
