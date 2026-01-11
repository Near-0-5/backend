"""chat 도메인 WebSocket 라우터.

여기에 넣을 것:
- websocket endpoint (예: /ws/chat/{stream_id})
- 연결 시 토큰 검증(Authorization header 또는 query param)
- 메시지 수신/검증 후 브로드캐스트(service 호출)
"""

from fastapi import APIRouter

router = APIRouter(prefix="", tags=["chat"])

# TODO: WebSocket endpoint 추가 (FastAPI WebSocket 사용)
