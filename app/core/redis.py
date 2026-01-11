"""Redis 클라이언트/유틸.

여기에 넣을 것:
- aioredis/redis.asyncio 기반 클라이언트 생성
- 채팅 pubsub, 캐시, rate limit 등에 사용 가능

주의:
- Celery broker/backend로 Redis를 쓴다면 URL/설정도 core/config.py에 두는 편이 깔끔.
"""
