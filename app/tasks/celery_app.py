"""Celery 앱 생성.

여기에 넣을 것:
- Celery('app', broker=..., backend=...)
- tasks autodiscover (notifications.tasks 등)
- 직렬화/타임존 설정

주의:
- FastAPI 앱과는 별도 프로세스로 worker를 실행함.
"""
