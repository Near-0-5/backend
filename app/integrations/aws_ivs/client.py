import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, Literal, ParamSpec, TypedDict, TypeVar, Unpack

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException
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
    StreamFiltersTypeDef,
    StreamKeySummaryTypeDef,
    StreamSessionSummaryTypeDef,
    StreamSummaryTypeDef,
    UpdateChannelRequestTypeDef,
    UpdateChannelResponseTypeDef,
)

from app.core.config import settings

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")


def ivs_errors(func: Callable[P, T]) -> Callable[P, T]:  # noqa: UP047
    """IVS API 호출 중 ClientError 발생 시 로깅 처리 데코레이터 함수"""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return func(*args, **kwargs)
        except ClientError as e:
            # 이미 처리(return)된 경우는 x
            # 처리되지 않은 예외만 로깅
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", "No message")

            logger.error(
                f"[IVS API Error] Method: {func.__name__} | "
                f"ErrorCode: {error_code} | ErrorMessage: {error_message}",
                extra={
                    "ivs_error_code": error_code,
                    "arguments": args[1:] if len(args) > 1 else [],  # self 제외
                    "keyword_arguments": kwargs,
                },
                exc_info=True,  # 스택 트레이스 포함
            )

            # 에러 코드별 HTTPException 매핑
            if error_code == "AccessDeniedException":
                raise HTTPException(status_code=500, detail="AWS IVS 권한이 부족합니다") from e

            elif error_code == "ResourceNotFoundException":
                raise HTTPException(
                    status_code=404, detail=f"IVS 리소스를 찾을 수 없습니다: {error_message}"
                ) from e

            elif error_code == "LimitExceededException":
                raise HTTPException(
                    status_code=429, detail="IVS 리소스 생성 한도를 초과했습니다"
                ) from e

            elif error_code == "ThrottlingException":
                raise HTTPException(
                    status_code=429,
                    detail="너무 많은 요청이 발생했습니다. 잠시 후 다시 시도해주세요",
                ) from e

            elif error_code == "ValidationException":
                raise HTTPException(
                    status_code=400, detail=f"잘못된 요청입니다: {error_message}"
                ) from e

            elif error_code == "ConflictException":
                raise HTTPException(
                    status_code=409, detail=f"리소스 충돌이 발생했습니다: {error_message}"
                ) from e

            elif error_code == "ServiceUnavailableException":
                raise HTTPException(
                    status_code=503, detail="AWS IVS 서비스를 일시적으로 사용할 수 없습니다"
                ) from e

            # 기타 AWS 에러
            else:
                raise HTTPException(
                    status_code=500, detail=f"IVS API 호출 실패: {error_message}"
                ) from e

    return wrapper


class ListChannelsFilters(TypedDict, total=False):
    """list_all_channels filter 옵션"""

    filterByName: str  # 채널 이름
    filterByRecordingConfigurationArn: str  # 녹화 설정 ARN
    filterByPlaybackRestrictionPolicyArn: str  # 재생 제한 정책 ARN


class ListLiveSteamsFilters(TypedDict, total=False):
    """list_live_streams filter 옵션"""

    # {'filterBy': {'health': 'HEALTHY'}} -> HEALTHY, STARVING, UNKNOWN
    filterBy: StreamFiltersTypeDef


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
    @ivs_errors
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

    @ivs_errors
    def create_channel(
        self,
        name: str,
        latency_mode: Literal["LOW", "NORMAL"] = "LOW",
        channel_type: Literal["STANDARD", "BASIC", "ADVANCED_SD", "ADVANCED_HD"] = "STANDARD",
        authorized: bool = True,
        recording_config_arn: str | None = None,
        preset: Literal["HIGHER_BANDWIDTH_DELIVERY", "CONSTRAINED_BANDWIDTH_DELIVERY"]
        | None = None,
    ) -> CreateChannelResponseTypeDef:
        """
        [생성] IVS 채널 생성 API 호출
        """

        params = CreateChannelRequestTypeDef(
            name=name,
            latencyMode=latency_mode,
            type=channel_type,
            authorized=authorized,
        )

        if recording_config_arn:
            params["recordingConfigurationArn"] = recording_config_arn

        if preset:
            params["preset"] = preset

        return self.client.create_channel(**params)

    @ivs_errors
    def get_channel(self, channel_arn: str) -> GetChannelResponseTypeDef:
        """
        [조회] 단일 AWS IVS 채널 상세 조회
        """
        try:
            return self.client.get_channel(arn=channel_arn)
        except ClientError as e:
            # 특정 에러 처리는 내부에서 하고, 나머지 에러는 raise 해서 데코레이터가 로깅함
            code = e.response.get("Error", {}).get("Code")
            if code == "ResourceNotFoundException":
                raise ValueError(f"Channel not found: {channel_arn}") from e
            raise

    @ivs_errors
    def batch_get_channel(self, arns: list[str]) -> BatchGetChannelResponseTypeDef:
        """
        [조회] 여러 AWS IVS 채널 정보 조회 (최대 50개)
        """

        return self.client.batch_get_channel(arns=arns)

    @ivs_errors
    def list_all_channels(
        self, **filters: Unpack[ListChannelsFilters]
    ) -> list[ChannelSummaryTypeDef]:
        """
        [목록] AWS IVS 채널 목록 페이지네이션
        - 필터링 옵션 (이름, 녹화 설정 ARN, 재생 제한 정책 ARN)
        - 필터링 옵션 동시에 사용하면 409
        """

        paginator = self.client.get_paginator("list_channels")
        channels: list[ChannelSummaryTypeDef] = []
        for page in paginator.paginate(**filters):
            channels.extend(page.get("channels", []))

        return channels

    @ivs_errors
    def update_channel(
        self, channel_arn: str, **kwargs: Unpack[UpdateChannelRequestTypeDef]
    ) -> UpdateChannelResponseTypeDef:
        """
        [수정] AWS IVS 채널 설정 수정
        """

        kwargs["arn"] = channel_arn
        return self.client.update_channel(**kwargs)

    @ivs_errors
    def delete_channel(self, channel_arn: str) -> None:
        """
        [삭제] AWS IVS 채널 삭제(공연 취소)
        """

        self.client.delete_channel(arn=channel_arn)

    # ===================== 스트림 키 관리 (Stream Keys) =====================

    @ivs_errors
    def create_stream_key(self, channel_arn: str) -> CreateStreamKeyResponseTypeDef:
        """
        [생성] 스트림 키 발급
        - 한 채널 당 기본 키 자동 생성
        - 추가 생성을 원하면 DeleteStreamKey 후 CreateStreamKey 해야 함
        """

        return self.client.create_stream_key(channelArn=channel_arn)

    @ivs_errors
    def get_stream_key(self, arn: str) -> GetStreamKeyResponseTypeDef:
        """
        [조회] 단일 키 정보 조회
        - 특정 스트림 키의 상세 정보와 실제 키 값 확인
        """

        return self.client.get_stream_key(arn=arn)

    @ivs_errors
    def batch_get_stream_key(self, arns: list[str]) -> BatchGetStreamKeyResponseTypeDef:
        """
        [조회] 여러 스트림 키 정보 조회
        """

        return self.client.batch_get_stream_key(arns=arns)

    @ivs_errors
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

    @ivs_errors
    def delete_stream_key(self, arn: str) -> None:
        """
        [삭제] 스트림 키 폐기(삭제)
        """

        self.client.delete_stream_key(arn=arn)

    # ===================== 스트림 상태 및 제어 =====================

    @ivs_errors
    def get_stream_health(self, channel_arn: str) -> GetStreamResponseTypeDef | None:
        """
        [상태] 실시간 송출 상태 확인
        - 방송 중이 아니면 None 반환
        """

        try:
            return self.client.get_stream(channelArn=channel_arn)
        except ClientError as e:
            # 예외를 여기서 처리하고 return하면 데코레이터는 에러로 인식하지 않음
            code = e.response.get("Error", {}).get("Code")
            if code == "ChannelNotBroadcasting":
                return None

            # 처리x 에러 rasie해서 데코레이터가 로깅
            raise

    @ivs_errors
    def list_live_streams(
        self, **filters: Unpack[ListLiveSteamsFilters]
    ) -> list[StreamSummaryTypeDef]:
        """
        [목록] LIVE 스트림 목록 조회
        - 스트림 상태 필터링 (HEALTHY, STARVING, UNKNOWN)
        """

        paginator = self.client.get_paginator("list_streams")
        streams: list[StreamSummaryTypeDef] = []

        for page in paginator.paginate(**filters):
            streams.extend(page.get("streams", []))
        return streams

    @ivs_errors
    def stop_stream(self, channel_arn: str) -> None:
        """
        [제어] 라이브 스트림을 강제 송출 중단
        """

        try:
            self.client.stop_stream(channelArn=channel_arn)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ["ResourceNotFoundException", "ChannelNotBroadcasting"]:
                return
            raise

    # ===================== 스트림 세션 및 통계 =====================

    @ivs_errors
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

    @ivs_errors
    def get_stream_session(
        self, channel_arn: str, stream_id: str
    ) -> GetStreamSessionResponseTypeDef:
        """
        [조회] 특정 방송 세션의 상세 지표 조회
        - 최대 동시 접속자 수, 시간대별 시청자 추이 그래프 데이터
        """
        return self.client.get_stream_session(channelArn=channel_arn, streamId=stream_id)
