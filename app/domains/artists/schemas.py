from datetime import date

from pydantic import BaseModel, HttpUrl

from app.domains.artists.models import GroupType


class ArtistListElement(BaseModel):
    id: int  # 모델 정의에 따라 string 또는 int 선택
    name: str
    profile_image: HttpUrl | str
    company: str | None
    description: str | None
    follower_count: int


class ArtistListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ArtistListElement]


class ArtistDetailResponse(BaseModel):
    id: int
    name: str
    profile_image: HttpUrl | str | None
    company: str | None
    description: str | None
    category: str | None
    debut_date: date | None
    member_count: int | None
    group_type: GroupType | None
    follower_count: int
