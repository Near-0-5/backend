from enum import Enum
from typing import TYPE_CHECKING

from tortoise import fields, models

if TYPE_CHECKING:
    from tortoise.fields import ForeignKeyRelation

    from app.domains.streams.models import ConcertSession


# 공연 장르 카테고리
class CategoryType(str, Enum):
    KPOP = "K-POP"
    TROT = "TROT"
    MUSICAL = "MUSICAL"
    BAND = "BAND"
    FAN_MEETING = "FAN_MEETING"
    KOREA_TOUR = "KOREA_TOUR"


class Concert(models.Model):
    """
    공연 메타 데이터
    - 특정 Category에 속함
    """

    id = fields.BigIntField(primary_key=True)
    category = fields.CharEnumField(
        CategoryType, default=CategoryType.KPOP, db_index=True, description="장르(category)"
    )
    title = fields.CharField(max_length=100, description="공연 제목")
    thumbnail_url = fields.CharField(
        max_length=255, null=True, description="공연 썸네일 사진(포스터 등)"
    )
    description = fields.TextField(null=True, description="콘서트 소개 글")

    created_at = fields.DatetimeField(auto_now_add=True, description="생성시각")
    updated_at = fields.DatetimeField(auto_now=True, description="수정시각")

    if TYPE_CHECKING:
        sessions: ForeignKeyRelation["ConcertSession"]

    class Meta:
        table = "concerts"

    def __str__(self) -> str:
        return f"{self.title} (id={self.id})"
