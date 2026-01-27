from pydantic import BaseModel, HttpUrl


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
