from tortoise.functions import Count

from app.domains.artists.models import Artist
from app.domains.artists.schemas import ArtistListElement, ArtistListResponse


class ArtistService:
    async def get_artists(
        self,
        page: int,
        page_size: int,
        search: str | None = None,
        category: str | None = None,
        sort_by: str = "latest",
    ) -> ArtistListResponse:
        """
        시스템 내 아티스트 목록을 조회합니다.
        검색(search)은 그룹명(stage_name)을 기준으로만 수행합니다.
        """
        # QuerySet 생성 및 팔로워 수 집계(Join) 준비
        query = Artist.all().annotate(follower_count=Count("followers"))

        # 그룹명(stage_name) 필터
        if search:
            query = query.filter(stage_name__icontains=search)

        # 카테고리 필터
        if category:
            query = query.filter(category_type=category)

        if sort_by == "follower":
            # 팔로워 많은 순, 같으면 최신순
            query = query.order_by("-follower_count", "-created_at")
        elif sort_by == "name":
            # 이름 가나다순
            query = query.order_by("stage_name")
        else:
            # 기본: 최신 등록순
            query = query.order_by("-created_at")

        # 전체 개수 조회 (페이징 전)
        total_count = await query.count()

        # 페이징 및 정렬
        offset = (page - 1) * page_size
        artists = await query.limit(page_size).offset(offset).all()

        # 5. 응답 객체 변환
        items = [
            ArtistListElement(
                id=artist.id,
                name=artist.stage_name,  # ERD의 stage_name을 그룹명으로 사용
                profile_image=artist.profile_img_url or "",
                company=artist.agency,
                description=artist.description,
                follower_count=getattr(artist, "follower_count", 0),
            )
            for artist in artists
        ]

        return ArtistListResponse(total=total_count, page=page, page_size=page_size, items=items)


artist_service = ArtistService()
