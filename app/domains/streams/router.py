from typing import Any

from fastapi import APIRouter, Body, Depends, Path

from app.api import deps
from app.domains.streams import deps as streams_deps
from app.domains.streams.service import StreamUserService
from app.domains.users.models import User

router = APIRouter(prefix="/streams", tags=["Streaming"])


@router.get(
    "/sessions/{session_id}/credentials",
    summary="스트림 시청 권한 확인 - 토큰 발급",
    description="실시간 스트리밍 시청을 위한 Playback URL과 인증 토큰을 발급합니다. \
                \n\n 비공개 채널의 경우 IVS Playback Token이 포함됩니다.",
)
async def get_stream_access(
    session_id: int = Path(..., description="콘서트 세션 ID"),
    current_user: User = Depends(deps.get_current_user),
    service: StreamUserService = Depends(streams_deps.get_stream_user_service),
) -> dict[str, Any]:
    """
    1. 유저의 세션 시청 자격(티켓 등)을 검증합니다.
    2. AWS IVS 채널 설정에 따라 Playback Token 서명 여부를 결정합니다.
    3. 채팅 서버 인증을 위한 내부 세션 토큰을 함께 반환합니다.
    """
    return await service.get_viewing_credentials(session_id, current_user)


@router.post(
    "/sessions/{session_id}/refresh",
    summary="시청 세션 연장 (토큰 재발급)",
    description="시청 중 토큰이 만료되기 전, 기존 리프레시 토큰을 사용해 세션을 연장합니다. \
                 \n\n 이때 유저의 시청 자격을 재검증합니다.",
)
async def refresh_stream_session(
    session_id: int = Path(..., description="콘서트 세션 ID"),
    refresh_token: str = Body(..., embed=True),  # json body에서 refresh_token 추출
    current_user: User = Depends(deps.get_current_user),
    service: StreamUserService = Depends(streams_deps.get_stream_user_service),
) -> dict[str, Any]:
    """
    1. 유저의 리프레시 토큰을 검증하고 새로운 Access/Refresh 토큰 세트를 생성합니다.
    2. 동시에 새로운 유효기간을 가진 AWS IVS 재생 토큰을 발급받아 반환합니다.
    """
    return await service.refresh_viewing_session(
        session_id,
        current_user,
        refresh_token,
    )
