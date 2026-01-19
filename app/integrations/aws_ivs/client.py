from typing import Any, Literal, TypedDict, cast

import boto3
from botocore.exceptions import ClientError
from mypy_boto3_ivs.type_defs import (
    BatchGetChannelResponseTypeDef,
    BatchGetStreamKeyResponseTypeDef,
    ChannelSummaryTypeDef,
    CreateChannelRequestTypeDef,
    CreateChannelResponseTypeDef,
    CreateStreamKeyResponseTypeDef,
    GetChannelResponseTypeDef,
    GetStreamKeyResponseTypeDef,
    GetStreamResponseTypeDef,
    GetStreamSessionResponseTypeDef,
    RecordingConfigurationSummaryTypeDef,
    StreamKeySummaryTypeDef,
    StreamSessionSummaryTypeDef,
    StreamSummaryTypeDef,
    UpdateChannelRequestTypeDef,
    UpdateChannelResponseTypeDef,
)

from app.core.config import settings


class IVSResponseErrorDetail(TypedDict):
    Code: str
    Message: str


class IVSClientErrorResponse(TypedDict):
    Error: IVSResponseErrorDetail


class IVSClient:
    def __init__(self) -> None:
        """
        Boto3 IVS 클라이언트 초기화
        - 로컬: settings 기반 자격 증명
        - 배포(IAM Role): boto3 기본 credential chain 사용
        """

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            self.client = boto3.client(
                "ivs",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
            )
        else:
            self.client = boto3.client("ivs", region_name=settings.AWS_REGION)

    # ===================== 녹화 설정 관리 (S3) =====================
    def list_recording_configurations(self) -> list[RecordingConfigurationSummaryTypeDef]:
        """
        [목록] 계정에 생성된 S3 녹화 설정 목록 조회
        - 채널 생성 시 'recording_config_arn' 선택
        """
        paginator = self.client.get_paginator("list_recording_configurations")
        configs: list[RecordingConfigurationSummaryTypeDef] = []
        for page in paginator.paginate():
            configs.extend(page.get("recordingConfigurations", []))
        return configs

    # ===================== 채널 관리 (Channels) =====================

    def create_channel(
        self,
        name: str,
        latency_mode: Literal["LOW", "NORMAL"] = "LOW",
        channel_type: Literal["STANDARD", "BASIC", "ADVANCED_SD", "ADVANCED_HD"] = "STANDARD",
        authorized: bool = True,
        recording_config_arn: str | None = None,
        preset: str | None = None,
    ) -> CreateChannelResponseTypeDef:
        """
        [생성] IVS 채널 생성 API 호출
        """

        params: CreateChannelRequestTypeDef = {
            "name": name,
            "latencyMode": latency_mode,
            "type": channel_type,
            "authorized": authorized,
        }

        if recording_config_arn:
            params["recordingConfigurationArn"] = recording_config_arn

        if preset:
            params["preset"] = cast("Any", preset)

        return self.client.create_channel(**params)

    def get_channel(self, channel_arn: str) -> GetChannelResponseTypeDef:
        """
        [조회] 단일 AWS IVS 채널 상세 조회
        """

        try:
            return self.client.get_channel(arn=channel_arn)
        except ClientError as e:
            err_resp: IVSClientErrorResponse = cast("IVSClientErrorResponse", e.response)
            if err_resp["Error"]["Code"] == "ResourceNotFoundException":
                raise ValueError(f"Channel not found: {channel_arn}") from e
            raise

    def batch_get_channel(self, arns: list[str]) -> BatchGetChannelResponseTypeDef:
        """
        [조회] 여러 AWS IVS 채널 정보 조회 (최대 50개)
        """

        return self.client.batch_get_channel(arns=arns)

    def list_all_channels(self, **filters: Any) -> list[ChannelSummaryTypeDef]:
        """
        [목록] AWS IVS 채널 목록 페이지네이션
        - 계정 내 모든 채널을 페이지네이션하여 리스트로 반환
        """

        paginator = self.client.get_paginator("list_channels")
        channels: list[ChannelSummaryTypeDef] = []
        for page in paginator.paginate(**filters):
            channels.extend(page.get("channels", []))

        return channels

    def update_channel(self, channel_arn: str, **kwargs: Any) -> UpdateChannelResponseTypeDef:
        """
        [수정] AWS IVS 채널 설정 수정
        """

        params = cast("UpdateChannelRequestTypeDef", {"arn": channel_arn, **kwargs})

        return self.client.update_channel(**params)

    def delete_channel(self, channel_arn: str) -> None:
        """
        [삭제] AWS IVS 채널 삭제(공연 취소)
        """

        self.client.delete_channel(arn=channel_arn)

    # ===================== 스트림 키 관리 (Stream Keys) =====================

    def create_stream_key(self, channel_arn: str) -> CreateStreamKeyResponseTypeDef:
        """
        [생성] 스트림 키 발급
        - 한 채널 당 기본 키 자동 생성
        - 추가 생성을 원하면 DeleteStreamKey 후 CreateStreamKey 해야 함
        """

        return self.client.create_stream_key(channelArn=channel_arn)

    def get_stream_key(self, arn: str) -> GetStreamKeyResponseTypeDef:
        """
        [조회] 단일 키 정보 조회
        - 특정 스트림 키의 상세 정보와 실제 키 값 확인
        """

        return self.client.get_stream_key(arn=arn)

    def batch_get_stream_key(self, arns: list[str]) -> BatchGetStreamKeyResponseTypeDef:
        """
        [조회] 여러 스트림 키 정보 조회
        """

        return self.client.batch_get_stream_key(arns=arns)

    def list_all_stream_keys(self, channel_arn: str) -> list[StreamKeySummaryTypeDef]:
        """
        [목록] 스트림 키 목록 페이지네이션
         - 특정 채널에 속한 모든 스트림 키 목록
        """

        paginator = self.client.get_paginator("list_stream_keys")
        keys: list[StreamKeySummaryTypeDef] = []

        for page in paginator.paginate(channelArn=channel_arn):
            keys.extend(page.get("streamKeys", []))

        return keys

    def delete_stream_key(self, arn: str) -> None:
        """
        [삭제] 스트림 키 폐기(삭제)
        """

        self.client.delete_stream_key(arn=arn)

    # ===================== 스트림 상태 및 제어 =====================

    def get_stream_health(self, channel_arn: str) -> GetStreamResponseTypeDef | None:
        """
        [상태] 실시간 송출 상태 확인
        - 방송 중이 아니면 None 반환
        """

        try:
            return self.client.get_stream(channelArn=channel_arn)
        except ClientError as e:
            if cast("dict[str, Any]", e.response)["Error"]["Code"] == "ChannelNotBroadcasting":
                return None
            raise

    def list_live_streams(self, **filters: Any) -> list[StreamSummaryTypeDef]:
        """
        [목록] LIVE 스트림 목록 조회
        - 현재 계정에서 실시간 송출 중인 모든 스트림 목록
        """

        paginator = self.client.get_paginator("list_streams")
        streams: list[StreamSummaryTypeDef] = []
        for page in paginator.paginate(**filters):
            streams.extend(page.get("streams", []))
        return streams

    def stop_stream(self, channel_arn: str) -> None:
        """
        [제어] 라이브 스트림을 강제 송출 중단
        """

        try:
            self.client.stop_stream(channelArn=channel_arn)
        except ClientError as e:
            code = cast("dict[str, Any]", e.response)["Error"]["Code"]
            if code not in ["ResourceNotFoundException", "ChannelNotBroadcasting"]:
                raise

    # ===================== 스트림 세션 및 통계 =====================
    def list_stream_sessions(self, channel_arn: str) -> list[StreamSessionSummaryTypeDef]:
        """
        [목록] 특정 채널의 과거 방송 세션 목록 조회
        - stubs에 get_paginator 타입 정의 누락으로 인해 직접 구현함
        """
        sessions: list[StreamSessionSummaryTypeDef] = []
        next_token: str | None = None

        while True:
            # 인자를 dict로 생성함
            params: dict[str, Any] = {"channelArn": channel_arn}

            if next_token:
                params["nextToken"] = next_token

            # API 호출
            response = self.client.list_stream_sessions(**params)
            sessions.extend(response.get("streamSessions", []))

            next_token = response.get("nextToken")
            if not next_token:
                break

        return sessions

    def get_stream_session(
        self, channel_arn: str, stream_id: str
    ) -> GetStreamSessionResponseTypeDef:
        """
        [조회] 특정 방송 세션의 상세 지표 조회
        - 최대 동시 접속자 수, 시간대별 시청자 추이 그래프 데이터
        """
        return self.client.get_stream_session(channelArn=channel_arn, streamId=stream_id)
