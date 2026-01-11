"""
app/domains/
- Django의 "apps"처럼 기능(도메인) 단위로 분리한 코드 영역.
- 각 도메인은 보통:
  - router.py: API 엔드포인트
  - schemas.py: 요청/응답 모델
  - service.py: 비즈니스 로직
  - models.py: DB 모델(Tortoise)
  - permissions.py: 권한 체크(필요한 경우)
"""
