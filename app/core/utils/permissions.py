from fastapi import HTTPException

from app.domains.users.models import User


class AdminPermission:
    @staticmethod
    def must_be_admin(user: User) -> None:
        if not user.is_superuser:
            raise HTTPException(403, "관리자만 접근이 가능합니다.")
