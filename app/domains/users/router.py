"""users 도메인 HTTP 라우터.

여기에 넣을 것:
- APIRouter(prefix='...', tags=[...])
- endpoints 정의(GET/POST/PATCH/DELETE)
- Depends로 인증/권한 체크
- service 함수를 호출해서 결과 반환

예:
- GET /users
- POST /users
"""

from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

# TODO: endpoints 추가
