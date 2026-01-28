import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.integrations.s3_client import S3Client


def setup_s3_mock(method_name, side_effect=None, return_value=None):
    mock_s3 = MagicMock()
    mock_method = AsyncMock(side_effect=side_effect, return_value=return_value)
    setattr(mock_s3, method_name, mock_method)

    # generate_presigned_url은 일반 비동기 메서드처럼 동작하도록 별도 설정
    if method_name == "generate_presigned_url":
        mock_s3.generate_presigned_url = AsyncMock(
            side_effect=side_effect, return_value=return_value
        )

    mock_client_cm = MagicMock()
    mock_client_cm.__aenter__ = AsyncMock(return_value=mock_s3)
    mock_client_cm.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.client.return_value = mock_client_cm
    return mock_session, mock_s3


@pytest.mark.asyncio
async def test_upload_client_error_coverage_47():
    """upload 메서드 ClientError 발생 테스트"""
    mock_session, _ = setup_s3_mock(
        "upload_fileobj",
        side_effect=ClientError({"Error": {"Code": "403", "Message": "Forbidden"}}, "Upload"),
    )

    with patch("app.integrations.s3_client.aioboto3.Session", return_value=mock_session):
        s3_client = S3Client()
        file = MagicMock(spec=io.BytesIO)
        file.name = "test.png"
        with pytest.raises(ClientError):
            await s3_client.upload(file)


@pytest.mark.asyncio
async def test_upload_with_key_seek_coverage_85_86():
    """file_obj.read()가 비어있을 때 seek(0) 동작 테스트"""
    file_obj = MagicMock()
    # 첫 호출 시 b"", 두 번째 호출 시 데이터 반환하도록 설정
    file_obj.read.side_effect = [b"", b"recovered content"]
    file_obj.seek.return_value = 0

    mock_session, mock_s3 = setup_s3_mock("put_object", return_value={})

    with patch("app.integrations.s3_client.aioboto3.Session", return_value=mock_session):
        s3_client = S3Client()
        await s3_client.upload_with_key(file_obj, "test_key")

        assert file_obj.seek.called
        assert mock_s3.put_object.call_args.kwargs["Body"] == b"recovered content"


@pytest.mark.asyncio
async def test_delete_object_client_error_coverage_105_109():
    """delete_object ClientError 발생 시 warning 로그 확인"""
    mock_session, _ = setup_s3_mock(
        "delete_object",
        side_effect=ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "Delete"),
    )

    with patch("app.integrations.s3_client.aioboto3.Session", return_value=mock_session):
        s3_client = S3Client()
        # 예외가 raise되지 않고 warning 로그만 남아야 함
        await s3_client.delete_object("missing_key")


@pytest.mark.asyncio
async def test_delete_prefix_no_contents_coverage_121_124():
    """삭제할 객체가 없을 때(Contents 미포함) 조기 종료 테스트"""
    # Contents 키가 없는 딕셔너리 반환
    mock_session, mock_s3 = setup_s3_mock("list_objects_v2", return_value={})
    mock_s3.delete_objects = AsyncMock()

    with patch("app.integrations.s3_client.aioboto3.Session", return_value=mock_session):
        s3_client = S3Client()
        await s3_client.delete_prefix("empty/prefix/")

        mock_s3.list_objects_v2.assert_awaited_once()
        mock_s3.delete_objects.assert_not_called()


@pytest.mark.asyncio
async def test_generate_presigned_url_error_coverage_139():
    """presigned_url 생성 실패 시 에러 스트링 반환 테스트"""
    mock_session, _ = setup_s3_mock(
        "generate_presigned_url",
        side_effect=ClientError({"Error": {"Code": "500", "Message": "InternalError"}}, "Presign"),
    )

    with patch("app.integrations.s3_client.aioboto3.Session", return_value=mock_session):
        s3_client = S3Client()
        result = await s3_client.generate_presigned_url("test_key")
        assert "An error occurred (500)" in result


def test_build_url_empty_key():
    """build_url의 key가 없을 때의 분기 테스트"""
    s3_client = S3Client()
    assert s3_client.build_url("") == ""
    assert "https://" in s3_client.build_url("some_key")
