import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException
from PIL import Image

from app.core.utils.image_resizer import ImageResizer
from app.integrations.s3_client import S3Client


@pytest.fixture
def mock_s3_session():
    """aioboto3 Session 모킹 헬퍼"""
    with patch("app.integrations.s3_client.aioboto3.Session") as mock_session_class:
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        yield mock_session


def setup_s3_method(mock_session, method_name, side_effect=None, return_value=None):
    """S3 클라이언트 메서드 동작 설정"""
    mock_s3 = MagicMock()
    mock_method = AsyncMock(side_effect=side_effect, return_value=return_value)
    setattr(mock_s3, method_name, mock_method)

    # Context Manager 설정 (__aenter__, __aexit__)
    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_client_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session.client.return_value = mock_client_cm
    return mock_s3


@pytest.mark.asyncio
async def test_s3_upload_client_error(mock_s3_session):
    """S3Client.upload: ClientError 발생 시 raise 확인"""
    setup_s3_method(
        mock_s3_session,
        "upload_fileobj",
        side_effect=ClientError({"Error": {"Code": "403"}}, "upload"),
    )

    client = S3Client()
    file = MagicMock(spec=io.BytesIO)
    file.name = "test.jpg"

    with pytest.raises(ClientError):
        await client.upload(file)


@pytest.mark.asyncio
async def test_s3_upload_with_key_seek(mock_s3_session):
    """S3Client.upload_with_key: 데이터가 비어있을 때 seek(0) 로직 확인"""
    file_obj = MagicMock()
    # 첫 read는 빈 값, 두 번째는 데이터 반환
    file_obj.read.side_effect = [b"", b"data"]
    file_obj.seek.return_value = 0

    setup_s3_method(mock_s3_session, "put_object", return_value={})

    client = S3Client()
    await client.upload_with_key(file_obj, "key")
    assert file_obj.seek.called


@pytest.mark.asyncio
async def test_s3_delete_object_warning(mock_s3_session):
    """S3Client.delete_object: ClientError 발생 시 raise하지 않고 종료"""
    setup_s3_method(
        mock_s3_session,
        "delete_object",
        side_effect=ClientError({"Error": {"Code": "404"}}, "delete"),
    )

    client = S3Client()
    await client.delete_object("missing_key")  # 에러 없이 통과해야 함


@pytest.mark.asyncio
async def test_s3_delete_prefix_no_contents(mock_s3_session):
    """S3Client.delete_prefix: 삭제할 객체가 없을 때"""
    mock_s3 = setup_s3_method(mock_s3_session, "list_objects_v2", return_value={})
    mock_s3.delete_objects = AsyncMock()

    client = S3Client()
    await client.delete_prefix("empty/")
    mock_s3.delete_objects.assert_not_called()


@pytest.mark.asyncio
async def test_s3_presigned_url_error(mock_s3_session):
    """S3Client.generate_presigned_url: 에러 발생 시 문자열 반환"""
    setup_s3_method(
        mock_s3_session,
        "generate_presigned_url",
        side_effect=ClientError({"Error": {"Code": "500"}}, "presign"),
    )

    client = S3Client()
    result = await client.generate_presigned_url("key")
    assert "An error occurred" in result


def test_s3_build_url_empty():
    """S3Client.build_url: 빈 키 입력 시 빈 문자열 반환"""
    assert S3Client().build_url("") == ""


@pytest.fixture
def mock_internal_s3():
    """ImageResizer에 주입할 모킹된 S3Client"""
    client = MagicMock(spec=S3Client)
    client.upload_with_key = AsyncMock()
    client.delete_prefix = AsyncMock()
    client.build_url.side_effect = lambda k: f"https://s3.com/{k}"
    return client


@pytest.fixture
def valid_img():
    img = Image.new("RGB", (10, 10), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    buf.name = "test.png"
    return buf


@pytest.mark.asyncio
async def test_resizer_init():
    """ImageResizer.__init__: S3Client 자동 생성 확인"""
    with patch("app.core.utils.image_resizer.S3Client") as mock_cls:
        resizer = ImageResizer()
        assert resizer.s3_client is not None
        mock_cls.assert_called_once()


@pytest.mark.asyncio
async def test_resizer_upload_success(mock_internal_s3, valid_img):
    resizer = ImageResizer(s3_client=mock_internal_s3)
    result = await resizer.upload_square_resizes(image_file=valid_img, sizes=(50,), path_prefix="p")
    assert "50" in result
    mock_internal_s3.upload_with_key.assert_awaited_once()


@pytest.mark.asyncio
async def test_resizer_upload_loop_exception(mock_internal_s3, valid_img):
    """ImageResizer: 루프 내부 에러 발생 시 500 에러"""
    resizer = ImageResizer(s3_client=mock_internal_s3)
    mock_internal_s3.upload_with_key.side_effect = Exception("Crash")

    with pytest.raises(HTTPException) as exc:
        await resizer.upload_square_resizes(image_file=valid_img, sizes=(50,), path_prefix="p")
    assert exc.value.status_code == 500


@pytest.mark.asyncio
async def test_resizer_delete_pattern_mismatch(mock_internal_s3):
    """ImageResizer: 잘못된 경로 패턴 차단"""
    resizer = ImageResizer(s3_client=mock_internal_s3)
    await resizer.delete_all_by_id_path("https://s3.com/invalid/path/img.png")
    mock_internal_s3.delete_prefix.assert_not_called()


@pytest.mark.asyncio
async def test_resizer_delete_exception_handling(mock_internal_s3):
    """ImageResizer: 삭제 중 예외 발생 시 로깅 후 무시"""
    resizer = ImageResizer(s3_client=mock_internal_s3)
    mock_internal_s3.delete_prefix.side_effect = Exception("S3 error")

    # 에러가 밖으로 나오지 않아야 함
    await resizer.delete_all_by_id_path("https://s3.com/users/1/profile/img.png")
    assert mock_internal_s3.delete_prefix.called
