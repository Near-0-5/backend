from datetime import date

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.domains.artists.models import GroupType


class ArtistBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    name: str = Field(
        ..., alias="stage_name", serialization_alias="name"
    )  # 필드명: name, DB: stage_name
    profile_image: HttpUrl | str | None = Field(
        None, alias="profile_img_url", serialization_alias="profile_image"
    )


class ArtistListElement(ArtistBase):
    company: str | None = Field(None, alias="agency")
    description: str | None
    follower_count: int


class ArtistListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ArtistListElement]


class ArtistDetailResponse(ArtistListElement):
    category: str = Field(..., alias="category_type")
    debut_date: date | None
    member_count: int | None
    group_type: GroupType | None
