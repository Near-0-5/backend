"""
app/
- FastAPI 프로젝트 루트 패키지.
- main.py에서 앱 생성/라이프사이클/라우터 조립을 담당.
- core/는 설정/공통 유틸.
- domains/는 Django의 "apps"처럼 기능 단위로 분리된 실제 비즈니스 코드.
- integrations/는 외부 연동(Kakao/Naver/AWS IVS 등).
- admin/는 fastapi-admin 관련 구성.
- tasks/는 celery 관련 구성(알림/비동기 작업).
"""
