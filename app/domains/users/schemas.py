from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
    name: str | None
    profile_image: str | None
    joined_at: datetime
    bio: str | None

    # 관계형 데이터
    favorite_artists: list[ArtistSimple]
    preferred_categories: list[str]
    notification_settings: NotiSettings
