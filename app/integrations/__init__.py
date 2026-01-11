"""
app/integrations/
- 외부 서비스 연동 모듈.
- Kakao/Naver OAuth, AWS IVS 같은 외부 API 호출은 여기로 모아두면 도메인이 깔끔해짐.
- domains/*/service.py에서는 integrations의 함수를 호출만 하도록 구성 추천.
"""
