from fastapi import HTTPException

from app.domains.streams.models import AccessLevel, ConcertSession
from app.domains.users.models import User


class StreamPermission:
    @staticmethod
    async def verify_playback_access(user: User, session: ConcertSession) -> None:
        """
        유저가 IVS 토큰을 발급받을 자격이 있는지 확인
        """
        if user.is_superuser or session.access_level == AccessLevel.PUBLIC:
            return

        if session.access_level == AccessLevel.ADMIN_ONLY:
            raise HTTPException(403, "테스트 중인 방송입니다.")

        # from app.domains.orders.models import UserTicket
        if session.access_level == AccessLevel.SPECIFIC:
            # TODO: 유료/무료 공연 기능 추가 -> 티켓 구매 여부 확인
            # has_ticket = await UserTicket.filter(
            #     user=user, concert=concert, is_valid=True
            # ).exists()
            # 지금은 없으니까 그냥 False로 에러 띄움
            has_ticket = False
            if not has_ticket:
                raise HTTPException(402, "티켓 구매가 필요한 공연입니다.")
