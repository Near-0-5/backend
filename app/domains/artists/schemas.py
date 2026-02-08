import datetime
from datetime import date

from fastapi import UploadFile
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


class ArtistRecommendationElement(ArtistBase):
    company: str | None = Field(None, alias="agency")
    follower_count: int
    recommendation_reason: str


class ArtistRecommendationResponse(BaseModel):
    recommended_artists: list[ArtistRecommendationElement]


class ArtistFormSchema(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    stage_name: str | None = Field(None, title="활동명")
    agency: str | None = Field(None, title="소속사")
    description: str | None = Field(None, title="소개")
    profile_img_url: UploadFile | None = Field(
        None, title="프로필 이미지", json_schema_extra={"widget": "upload", "form_widget": "upload"}
    )
    debut_date: datetime.date | None = Field(None, title="데뷔일")
    member_count: int | None = Field(0, title="멤버 수")
    group_type: str | None = Field(None, title="그룹형태")
    category_type: str | None = Field(None, title="카테고리")
