import asyncio
from collections import defaultdict
from typing import DefaultDict, Set
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self) -> None:
        """
        self._room: room_id(채팅방)에 연결된 ws(접속자)을 저장하는 자료구조.
        self._lock: 여러 코루틴(connect/disconnect/broadcast)이 동시에 self._rooms를 수정할 때
        레이스 컨디션이 생기지 않도록, self._rooms 수정 구간을 한 번에 하나씩만 실행되게 보호하는 asyncio 락
        """
        self._rooms: DefaultDict[str, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, ws: WebSocket) -> None:
        """
        WebSocket 연결을 수락하고, 해당 room_id(채팅방)의 접속자 목록에 ws(접속자)를 등록한다땃.

        Args:
            room_id (str): 유저가 참여할 채팅방 식별자
            ws (WebSocket): 유저 1명과 서버 사이의 WebSocket 연결 객체(통로)

        Flow:
            1) ws.accept()로 WebSocket 핸드셰이크를 수락한다.
            2) self._lock(락)으로 보호된 임계구역에서 self._rooms[room_id]에 ws를 추가한다.
            (동시에 connect/disconnect가 실행되더라도 _rooms 상태가 꼬이지 않게 하기 위함)
        """
        await ws.accept()
        async with self._lock:
            self._rooms[room_id].add(ws)

    async def disconnect(self, room_id: str, ws: WebSocket) -> None:
        """
        해당 room_id의 접속자 목록에서 ws(접속자)를 제거한다.

        Flow:
            1) self._lock(락)으로 보호된 임계구역에서 self._rooms[room_id]에서 해당 ws를 제거한다.
            2) 만약 self._rooms[room_id]가 빈 상태이면 해당 room_id 또한 삭제한다. 
        """
        async with self._lock:
            self._rooms[room_id].discard(ws)
            if not self._rooms[room_id]:
                self._rooms.pop(room_id, None)

    async def broadcast_json(self, room_id: str, payload: dict) -> None:
        """
        특정 room_id(채팅방)에 연결된 모든 WebSocket(접속자)에게 payload(JSON)를 브로드캐스트한다땃.

        Args:
            room_id (str): 브로드캐스트 대상 채팅방 식별자
            payload (dict): 각 클라이언트에게 전송할 JSON 데이터

        Flow:
            1) self._lock으로 보호된 임계구역에서, 해당 room_id에 연결된 ws 목록을 '복사'해서 targets로 만든다.
            - 락을 오래 잡지 않기 위해, 실제 전송(send)은 락 밖에서 수행한다.
            2) targets에 있는 각 ws에 대해 ws.send_json(payload)로 전송한다.
            3) 전송 중 예외가 발생한 ws는 dead 리스트에 모아둔다. (끊어진/비정상 연결 가능성)
            4) dead가 있으면 다시 락을 잡고, 해당 ws들을 room에서 제거(discard)한다.
            5) 제거 후 방이 비었으면(room에 ws가 0개) room_id 키를 pop하여 메모리에서 정리한다.
        """
        async with self._lock:
            targets = list(self._rooms.get(room_id, set()))

        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms[room_id].discard(ws)
                if room_id in self._rooms and not self._rooms[room_id]:
                    self._rooms.pop(room_id, None)