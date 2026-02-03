from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.integrations.aws_ivs.client import IVSClient

if TYPE_CHECKING:
    from mypy_boto3_ivs.type_defs import (
        BatchGetChannelResponseTypeDef,
        BatchGetStreamKeyResponseTypeDef,
        CreateChannelResponseTypeDef,
        CreateStreamKeyResponseTypeDef,
        GetChannelResponseTypeDef,
        GetStreamKeyResponseTypeDef,
        GetStreamResponseTypeDef,
        GetStreamSessionResponseTypeDef,
        UpdateChannelResponseTypeDef,
    )


@pytest.fixture
def mock_boto3_client():
    """Boto3 클라이언트 모킹"""
    with patch("app.integrations.aws_ivs.client.boto3.client") as mock_client:
        yield mock_client


@pytest.fixture
def ivs_client(mock_boto3_client):
    """IVSClient 인스턴스 픽스처"""
    return IVSClient()


class TestIVSClientInit:
    """IVS 클라이언트 초기화 테스트"""

    @patch("app.integrations.aws_ivs.client.settings")
    @patch("app.integrations.aws_ivs.client.boto3.client")
    def test_init_with_credentials(self, mock_client, mock_settings):
        """자격 증명이 있을 때 초기화"""
        mock_settings.AWS_ACCESS_KEY_ID = "test_key"
        mock_settings.AWS_SECRET_ACCESS_KEY = "test_secret"
        mock_settings.AWS_REGION = "us-east-1"

        IVSClient()

        mock_client.assert_called_once_with(
            "ivs",
            aws_access_key_id="test_key",
            aws_secret_access_key="test_secret",
            region_name="us-east-1",
        )

    @patch("app.integrations.aws_ivs.client.settings")
    @patch("app.integrations.aws_ivs.client.boto3.client")
    def test_init_without_credentials(self, mock_client, mock_settings):
        """자격 증명이 없을 때 초기화 (IAM Role 사용)"""
        mock_settings.AWS_ACCESS_KEY_ID = None
        mock_settings.AWS_SECRET_ACCESS_KEY = None
        mock_settings.AWS_REGION = "ap-northeast-2"

        IVSClient()

        mock_client.assert_called_once_with("ivs", region_name="ap-northeast-2")


class TestRecordingConfigurations:
    """녹화 설정 관리 테스트"""

    def test_list_recording_configurations(self, ivs_client):
        """녹화 설정 목록 조회"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"recordingConfigurations": [{"arn": "arn:config:1"}]},
            {"recordingConfigurations": [{"arn": "arn:config:2"}]},
        ]
        ivs_client.client.get_paginator.return_value = mock_paginator

        result = ivs_client.list_recording_configurations()

        assert len(result) == 2
        assert result[0]["arn"] == "arn:config:1"
        assert result[1]["arn"] == "arn:config:2"
        ivs_client.client.get_paginator.assert_called_once_with("list_recording_configurations")


class TestChannelManagement:
    """채널 관리 테스트"""

    def test_create_channel_minimal(self, ivs_client):
        """최소 파라미터로 채널 생성"""
        expected_response: CreateChannelResponseTypeDef = {
            "channel": {"arn": "arn:channel:123", "name": "test-channel"}
        }
        ivs_client.client.create_channel.return_value = expected_response

        result = ivs_client.create_channel(name="test-channel")

        assert result == expected_response
        ivs_client.client.create_channel.assert_called_once()
        call_args = ivs_client.client.create_channel.call_args[1]
        assert call_args["name"] == "test-channel"
        assert call_args["latencyMode"] == "LOW"
        assert call_args["type"] == "STANDARD"
        assert call_args["authorized"] is True

    def test_create_channel_with_all_params(self, ivs_client):
        """모든 파라미터로 채널 생성"""
        ivs_client.client.create_channel.return_value = {}

        ivs_client.create_channel(
            name="full-channel",
            latency_mode="NORMAL",
            channel_type="ADVANCED_HD",
            authorized=False,
            recording_config_arn="arn:recording:config",
            preset="HIGHER_BANDWIDTH_DELIVERY",
        )

        call_args = ivs_client.client.create_channel.call_args[1]
        assert call_args["name"] == "full-channel"
        assert call_args["latencyMode"] == "NORMAL"
        assert call_args["type"] == "ADVANCED_HD"
        assert call_args["authorized"] is False
        assert call_args["recordingConfigurationArn"] == "arn:recording:config"
        assert call_args["preset"] == "HIGHER_BANDWIDTH_DELIVERY"

    def test_get_channel_success(self, ivs_client):
        """채널 조회 성공"""
        expected_response: GetChannelResponseTypeDef = {
            "channel": {"arn": "arn:channel:123", "name": "test"}
        }
        ivs_client.client.get_channel.return_value = expected_response

        result = ivs_client.get_channel("arn:channel:123")

        assert result == expected_response
        ivs_client.client.get_channel.assert_called_once_with(arn="arn:channel:123")

    def test_get_channel_not_found(self, ivs_client):
        """채널 조회 실패 - 존재하지 않음"""
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
        ivs_client.client.get_channel.side_effect = ClientError(error_response, "GetChannel")

        with pytest.raises(ValueError, match="Channel not found"):
            ivs_client.get_channel("arn:channel:nonexistent")

    def test_get_channel_other_error(self, ivs_client):
        """채널 조회 실패 - 기타 에러"""
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}
        ivs_client.client.get_channel.side_effect = ClientError(error_response, "GetChannel")

        with pytest.raises(HTTPException) as exc:
            ivs_client.get_channel("arn:channel:123")

        assert exc.value.status_code == 500

    def test_batch_get_channel(self, ivs_client):
        """여러 채널 조회"""
        expected_response: BatchGetChannelResponseTypeDef = {
            "channels": [{"arn": "arn:1"}, {"arn": "arn:2"}],
            "errors": [],
        }
        ivs_client.client.batch_get_channel.return_value = expected_response

        result = ivs_client.batch_get_channel(["arn:1", "arn:2"])

        assert result == expected_response
        ivs_client.client.batch_get_channel.assert_called_once_with(arns=["arn:1", "arn:2"])

    def test_list_all_channels(self, ivs_client):
        """채널 목록 조회"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"channels": [{"arn": "arn:1"}]},
            {"channels": [{"arn": "arn:2"}, {"arn": "arn:3"}]},
        ]
        ivs_client.client.get_paginator.return_value = mock_paginator

        result = ivs_client.list_all_channels()

        assert len(result) == 3
        ivs_client.client.get_paginator.assert_called_once_with("list_channels")

    def test_list_all_channels_with_filters(self, ivs_client):
        """필터 적용하여 채널 목록 조회"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"channels": []}]
        ivs_client.client.get_paginator.return_value = mock_paginator

        ivs_client.list_all_channels(filterByName="test")

        mock_paginator.paginate.assert_called_once_with(filterByName="test")

    def test_update_channel(self, ivs_client):
        """채널 수정"""
        expected_response: UpdateChannelResponseTypeDef = {
            "channel": {"arn": "arn:channel:123", "name": "updated"}
        }
        ivs_client.client.update_channel.return_value = expected_response

        result = ivs_client.update_channel("arn:channel:123", name="updated", latencyMode="NORMAL")

        assert result == expected_response
        call_args = ivs_client.client.update_channel.call_args[1]
        assert call_args["arn"] == "arn:channel:123"
        assert call_args["name"] == "updated"
        assert call_args["latencyMode"] == "NORMAL"

    def test_delete_channel(self, ivs_client):
        """채널 삭제"""
        ivs_client.client.delete_channel.return_value = {}

        ivs_client.delete_channel("arn:channel:123")

        ivs_client.client.delete_channel.assert_called_once_with(arn="arn:channel:123")


class TestStreamKeyManagement:
    """스트림 키 관리 테스트"""

    def test_create_stream_key(self, ivs_client):
        """스트림 키 생성"""
        expected_response: CreateStreamKeyResponseTypeDef = {
            "streamKey": {"arn": "arn:key:123", "value": "sk_test_key"}
        }
        ivs_client.client.create_stream_key.return_value = expected_response

        result = ivs_client.create_stream_key("arn:channel:123")

        assert result == expected_response
        ivs_client.client.create_stream_key.assert_called_once_with(channelArn="arn:channel:123")

    def test_get_stream_key(self, ivs_client):
        """스트림 키 조회"""
        expected_response: GetStreamKeyResponseTypeDef = {
            "streamKey": {"arn": "arn:key:123", "value": "sk_test"}
        }
        ivs_client.client.get_stream_key.return_value = expected_response

        result = ivs_client.get_stream_key("arn:key:123")

        assert result == expected_response
        ivs_client.client.get_stream_key.assert_called_once_with(arn="arn:key:123")

    def test_batch_get_stream_key(self, ivs_client):
        """여러 스트림 키 조회"""
        expected_response: BatchGetStreamKeyResponseTypeDef = {
            "streamKeys": [{"arn": "arn:1"}, {"arn": "arn:2"}],
            "errors": [],
        }
        ivs_client.client.batch_get_stream_key.return_value = expected_response

        result = ivs_client.batch_get_stream_key(["arn:1", "arn:2"])

        assert result == expected_response
        ivs_client.client.batch_get_stream_key.assert_called_once_with(arns=["arn:1", "arn:2"])

    def test_list_all_stream_keys(self, ivs_client):
        """스트림 키 목록 조회"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"streamKeys": [{"arn": "arn:1"}]},
            {"streamKeys": [{"arn": "arn:2"}]},
        ]
        ivs_client.client.get_paginator.return_value = mock_paginator

        result = ivs_client.list_all_stream_keys("arn:channel:123")

        assert len(result) == 2
        ivs_client.client.get_paginator.assert_called_once_with("list_stream_keys")
        mock_paginator.paginate.assert_called_once_with(channelArn="arn:channel:123")

    def test_delete_stream_key(self, ivs_client):
        """스트림 키 삭제"""
        ivs_client.client.delete_stream_key.return_value = {}

        ivs_client.delete_stream_key("arn:key:123")

        ivs_client.client.delete_stream_key.assert_called_once_with(arn="arn:key:123")


class TestStreamHealthAndControl:
    """스트림 상태 및 제어 테스트"""

    def test_get_stream_health_broadcasting(self, ivs_client):
        """방송 중일 때 스트림 상태 조회"""
        expected_response: GetStreamResponseTypeDef = {
            "stream": {"state": "LIVE", "health": "HEALTHY"}
        }
        ivs_client.client.get_stream.return_value = expected_response

        result = ivs_client.get_stream_health("arn:channel:123")

        assert result == expected_response
        ivs_client.client.get_stream.assert_called_once_with(channelArn="arn:channel:123")

    def test_get_stream_health_not_broadcasting(self, ivs_client):
        """방송 중이 아닐 때 스트림 상태 조회"""
        error_response = {
            "Error": {"Code": "ChannelNotBroadcasting", "Message": "Channel not broadcasting"}
        }
        ivs_client.client.get_stream.side_effect = ClientError(error_response, "GetStream")

        result = ivs_client.get_stream_health("arn:channel:123")

        assert result is None

    def test_get_stream_health_other_error(self, ivs_client):
        """스트림 상태 조회 - 기타 에러"""
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
        ivs_client.client.get_stream.side_effect = ClientError(error_response, "GetStream")

        with pytest.raises(HTTPException) as exc:
            ivs_client.get_stream_health("arn:channel:123")

        assert exc.value.status_code == 500

    def test_list_live_streams(self, ivs_client):
        """라이브 스트림 목록 조회"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"streams": [{"state": "LIVE"}]},
            {"streams": [{"state": "LIVE"}]},
        ]
        ivs_client.client.get_paginator.return_value = mock_paginator

        result = ivs_client.list_live_streams()

        assert len(result) == 2
        ivs_client.client.get_paginator.assert_called_once_with("list_streams")

    def test_list_live_streams_with_filters(self, ivs_client):
        """필터 적용하여 라이브 스트림 목록 조회"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"streams": []}]
        ivs_client.client.get_paginator.return_value = mock_paginator

        ivs_client.list_live_streams(filterByChannelArn="arn:channel:123")

        mock_paginator.paginate.assert_called_once_with(filterByChannelArn="arn:channel:123")

    def test_stop_stream_success(self, ivs_client):
        """스트림 중단 성공"""
        ivs_client.client.stop_stream.return_value = {}

        ivs_client.stop_stream("arn:channel:123")

        ivs_client.client.stop_stream.assert_called_once_with(channelArn="arn:channel:123")

    def test_stop_stream_not_found(self, ivs_client):
        """스트림 중단 - 채널 없음 (무시)"""
        error_response = {"Error": {"Code": "ResourceNotFoundException", "Message": "Not found"}}
        ivs_client.client.stop_stream.side_effect = ClientError(error_response, "StopStream")

        # 예외가 발생하지 않아야 함
        ivs_client.stop_stream("arn:channel:123")

    def test_stop_stream_not_broadcasting(self, ivs_client):
        """스트림 중단 - 방송 중 아님 (무시)"""
        error_response = {
            "Error": {"Code": "ChannelNotBroadcasting", "Message": "Not broadcasting"}
        }
        ivs_client.client.stop_stream.side_effect = ClientError(error_response, "StopStream")

        # 예외가 발생하지 않아야 함
        ivs_client.stop_stream("arn:channel:123")

    def test_stop_stream_other_error(self, ivs_client):
        """스트림 중단 - 기타 에러"""
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "Access denied"}}
        ivs_client.client.stop_stream.side_effect = ClientError(error_response, "StopStream")

        with pytest.raises(HTTPException) as exc:
            ivs_client.stop_stream("arn:channel:123")

        assert exc.value.status_code == 500


class TestStreamSessions:
    """스트림 세션 및 통계 테스트"""

    def test_list_stream_sessions_single_page(self, ivs_client):
        """스트림 세션 목록 조회 - 단일 페이지"""
        ivs_client.client.list_stream_sessions.return_value = {
            "streamSessions": [{"streamId": "session1"}, {"streamId": "session2"}],
        }

        result = ivs_client.list_stream_sessions("arn:channel:123")

        assert len(result) == 2
        assert result[0]["streamId"] == "session1"
        ivs_client.client.list_stream_sessions.assert_called_once_with(channelArn="arn:channel:123")

    def test_list_stream_sessions_multiple_pages(self, ivs_client):
        """스트림 세션 목록 조회 - 여러 페이지"""
        ivs_client.client.list_stream_sessions.side_effect = [
            {
                "streamSessions": [{"streamId": "s1"}],
                "nextToken": "token1",
            },
            {
                "streamSessions": [{"streamId": "s2"}],
                "nextToken": "token2",
            },
            {
                "streamSessions": [{"streamId": "s3"}],
            },
        ]

        result = ivs_client.list_stream_sessions("arn:channel:123")

        assert len(result) == 3
        assert ivs_client.client.list_stream_sessions.call_count == 3

        # 첫 번째 호출
        first_call = ivs_client.client.list_stream_sessions.call_args_list[0]
        assert first_call[1] == {"channelArn": "arn:channel:123"}

        # 두 번째 호출 (nextToken 포함)
        second_call = ivs_client.client.list_stream_sessions.call_args_list[1]
        assert second_call[1] == {"channelArn": "arn:channel:123", "nextToken": "token1"}

    def test_get_stream_session(self, ivs_client):
        """스트림 세션 상세 조회"""
        expected_response: GetStreamSessionResponseTypeDef = {
            "streamSession": {
                "streamId": "stream123",
                "channel": {"arn": "arn:channel:123"},
            }
        }
        ivs_client.client.get_stream_session.return_value = expected_response

        result = ivs_client.get_stream_session("arn:channel:123", "stream123")

        assert result == expected_response
        ivs_client.client.get_stream_session.assert_called_once_with(
            channelArn="arn:channel:123", streamId="stream123"
        )


class TestEdgeCases:
    """엣지 케이스 테스트"""

    def test_empty_pagination_result(self, ivs_client):
        """빈 페이지네이션 결과"""
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"channels": []}]
        ivs_client.client.get_paginator.return_value = mock_paginator

        result = ivs_client.list_all_channels()

        assert result == []

    def test_list_stream_sessions_empty(self, ivs_client):
        """세션 목록 없음"""
        ivs_client.client.list_stream_sessions.return_value = {"streamSessions": []}

        result = ivs_client.list_stream_sessions("arn:channel:123")

        assert result == []
