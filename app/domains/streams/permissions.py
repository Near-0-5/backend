from fastapi import HTTPException

from app.domains.streams.models import AccessLevel, Concert
from app.domains.users.models import User


class StreamPermission:
    @staticmethod
    def must_be_admin(user: User) -> None:
        if not user.is_superuser:
            raise HTTPException(403, "관리자만 접근이 가능합니다.")

    @staticmethod
    async def verify_playback_access(user: User, concert: Concert) -> None:
        """
        유저가 IVS 토큰을 발급받을 자격이 있는지 확인
        """
        if user.is_superuser or concert.access_level == AccessLevel.PUBLIC:
            return

        if concert.access_level == AccessLevel.ADMIN_ONLY:
            raise HTTPException(403, "테스트 중인 방송입니다.")

        # from app.domains.orders.models import UserTicket
        if concert.access_level == AccessLevel.SPECIFIC:
            # TODO: 유료/무료 공연 기능 추가 -> 티켓 구매 여부 확인
            # has_ticket = await UserTicket.filter(
            #     user=user, concert=concert, is_valid=True
            # ).exists()
            # 지금은 없으니까 그냥 False로 에러 띄움
            has_ticket = False
            if not has_ticket:
                raise HTTPException(402, "티켓 구매가 필요한 공연입니다.")
