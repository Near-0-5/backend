"""공통 Depends 모음.

여기에 넣을 것(추천):
- get_current_user: JWT로 현재 로그인 유저 가져오기
- require_admin: 관리자 권한 체크
- pagination params, common query params 등

팁:
- FastAPI는 Django의 middleware/permission 느낌을 Depends로 많이 풀어냄.
"""

from __future__ import annotations

from fastapi import Depends

# TODO: JWT 인증 로직이 생기면 여기서 current user dependency를 제공
def get_current_user():
    """현재 로그인 유저를 반환하는 Depends 자리.

    구현 예:
    - Authorization: Bearer <token> 파싱
    - 토큰 검증 후 user_id 추출
    - DB에서 User 조회
    """
    raise NotImplementedError
