"""Kakao OAuth 연동 모듈.

여기에 넣을 것:
- code -> access_token 교환 요청(httpx)
- access_token -> 사용자 프로필 조회 요청
- (필요하면) 토큰 갱신/만료 처리

domains/auth/service.py 에서 이 모듈을 호출해서
'소셜 프로필 -> 우리 서비스 User upsert' 흐름을 만들면 됨.
"""
