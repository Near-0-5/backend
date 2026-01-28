from datetime import datetime

from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.domains.notifications.models import UserNoti
from app.domains.streams.models import CategoryType
from app.domains.users.models import User, UserCatFav


class ArtistSimple(BaseModel):
    id: int
    name: str
    profile_image: str | None


class NotiSettings(BaseModel):
    new_content_from_favorite_artists: bool
    live_start_notification: bool
    marketing_consent: bool


class UserMeResponse(BaseModel):
    # class Config: ... 대체
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None
    nickname: str
    name: str | None = Field(alias="real_name")
    profile_image: str | None = Field(alias="profile_img_url")
    created_at: datetime
    bio: str | None

    # 관계형 데이터
    favorite_artists: list[ArtistSimple]
    preferred_categories: list[str]
    notification_settings: NotiSettings

    @classmethod
    def from_orm_user_profile_custom(
        cls, user: User, notis: UserNoti | None, fav_cats: list[UserCatFav]
    ) -> "UserMeResponse":
        """모델 객체들을 받아 스키마 인스턴스로 변환하는 팩토리 메서드"""
        return cls(
            id=user.id,
            email=user.email,
            nickname=user.nickname,
            real_name=user.real_name,
            profile_img_url=user.profile_img_url,
            created_at=user.created_at,
            bio=user.bio,
            favorite_artists=[
                ArtistSimple(id=a.id, name=a.stage_name, profile_image=a.profile_img_url)
                for a in user.followed_artists
            ],
            preferred_categories=[c.category.value for c in fav_cats],
            notification_settings=NotiSettings(
                new_content_from_favorite_artists=notis.artist_noti if notis else True,
                live_start_notification=notis.live_noti if notis else True,
                marketing_consent=notis.marketing_noti if notis else False,
            ),
        )


class UserMeUpdate(BaseModel):
    nickname: str | None = Field(None, min_length=2, max_length=20, pattern=r"^[a-zA-Z0-9_가-힣]+$")
    notification_settings: NotiSettings | None = None
    bio: str | None = Field(None, max_length=500)
    profile_image: UploadFile | None = None
    updated_at: datetime


class FavoriteArtistItem(BaseModel):
    id: int
    stage_name: str
    profile_img_url: str | None
    category: CategoryType
    group_type: str | None
    member_count: int | None
    agency: str | None
    followed_at: datetime  # (alias="follows.created_at")


class FavoriteArtistListResponse(BaseModel):
    total: int
    items: list[FavoriteArtistItem]
