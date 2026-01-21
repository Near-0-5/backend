from enum import Enum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from app.domains.streams.models import ConcertSession
    from app.domains.users.models import User


class OrderStatus(str, Enum):
    PENDING = "PENDING"  # 결제 대기
    PAID = "PAID"  # 결제 완료
    CANCELLED = "CANCELLED"  # 취소됨
    REFUNDED = "REFUNDED"  # 환불됨


class Order(models.Model):
    """
    결제 기록 테이블
    - PG사 승인 번호와 실제 결제 금액 관리
    """

    id = fields.BigIntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="orders"
    )
    session: fields.ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession", related_name="orders"
    )
    order_no = fields.CharField(max_length=100, unique=True)  # 서비스 고유 주문번호
    imp_uid = fields.CharField(max_length=100, null=True)  # 포트원 등 PG사 식별번호

    amount = fields.IntField(default=0)  # 결제 금액
    status = fields.CharEnumField(OrderStatus, default=OrderStatus.PENDING)

    paid_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "orders"


class UserTicket(models.Model):
    """
    시청 권한 테이블 (StreamPermission이 조회할 대상)
    - Order가 'PAID' 상태일 때 이 레코드가 유효함
    """

    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User", related_name="tickets"
    )
    session: fields.ForeignKeyRelation["ConcertSession"] = fields.ForeignKeyField(
        "models.ConcertSession", related_name="tickets"
    )
    order: fields.OneToOneRelation["Order"] = fields.OneToOneField(
        "models.Order", related_name="ticket"
    )

    is_valid = fields.BooleanField(default=True)  # 환불 시 False 처리
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "user_tickets"
        unique_together = (("user", "concert"),)  # 중복 시청권 방지
