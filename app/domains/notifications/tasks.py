"""notifications 관련 Celery task 엔트리포인트.

여기에 넣을 것:
- send_live_notification(stream_id, ...)
- 예약 알림(라이브 시작 전 n분)
- 실패 재시도 정책

주의:
- tasks/celery_app.py의 celery 인스턴스를 import해서 사용.
"""
