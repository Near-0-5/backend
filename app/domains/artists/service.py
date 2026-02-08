import json
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile, status
from tortoise.functions import Count

from app.core.config import settings
from app.core.redis import redis_client
from app.core.utils.image_resizer import ImageResizer
from app.domains.artists.models import Artist, Follow
from app.domains.artists.schemas import ArtistDetailResponse, ArtistListElement, ArtistListResponse

# Ruff TC003: 타입 힌트용 임포트를 체크 블록으로 이동
if TYPE_CHECKING:
    from collections.abc import Iterable


class ArtistService:
    def _get_full_image_url(self, path: str | None) -> str:
        """
        DB에 저장된 경로를 확인하여 전체 URL을 반환합니다.
        이미 https://로 시작하면 그대로 반환하고, 아니면 CloudFront 도메인을 붙입니다.
        """
        if not path:
            return ""

        # 이미 전체 URL(https://)이 저장되어 있는 경우 그대로 반환
        if path.startswith("https://"):
            return path

        # 상대 경로인 경우 CloudFront 도메인 결합
        base_url = settings.CLOUDFRONT_DOMAIN.rstrip("/")
        clean_path = path.lstrip("/")
        return f"{base_url}/{clean_path}"

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
                profile_image=self._get_full_image_url(artist.profile_img_url),
                company=artist.agency,
                description=artist.description,
                follower_count=getattr(artist, "follower_count", 0),
            )
            for artist in artists
        ]

        return ArtistListResponse(total=total_count, page=page, page_size=page_size, items=items)

    async def get_artist_detail(self, artist_id: int) -> ArtistDetailResponse:
        # 아티스트 조회 및 팔로워 수 집계
        artist = (
            await Artist.filter(id=artist_id).annotate(follower_count=Count("followers")).first()
        )

        if not artist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="요청하신 아티스트를 찾을 수 없습니다.",
            )

        return ArtistDetailResponse(
            id=artist.id,
            name=artist.stage_name,  #
            profile_image=self._get_full_image_url(artist.profile_img_url),
            company=artist.agency,  #
            description=artist.description,  #
            category=artist.category_type,  #
            debut_date=artist.debut_date,  #
            member_count=artist.member_count,  #
            group_type=artist.group_type,  #
            follower_count=getattr(artist, "follower_count", 0),  #
        )

    async def _get_fallback_artists(
        self, limit: int, exclude_ids: list[int] | None = None
    ) -> list[Any]:
        """최신 등록 순으로 아티스트를 가져오는 공통 로직"""
        query = Artist.all().annotate(follower_count=Count("followers"))
        if exclude_ids:
            query = query.filter(id__not_in=exclude_ids)
        return await query.order_by("-created_at").limit(limit)

    async def get_personalized_recommendations(
        self, user_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        사용자 기반 협업 필터링 (Redis 캐싱 적용)
        """
        limit = min(limit, 50)  # 상한 50
        cache_key = f"user_recommendation:{user_id}"

        # Redis에서 캐시된 결과 확인
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return cast("list[dict[str, Any]]", json.loads(cached_data))

        # 캐시가 없으면 나와 팔로우가 겹치는 유저 기반으로 아티스트 추천 시작
        # 내 팔로우 목록 가져오기
        my_follows = await Follow.filter(user_id=user_id).values_list("artist_id", flat=True)
        recommended_artists = []
        reason = "회원님이 좋아하실만한 아티스트"  # 팔로우는 있지만 유사 사용자가 없을경우 출력

        if not my_follows:
            # 팔로우가 전혀 없는 경우: 최신 아티스트추천 + 팔로워 집계 (Cold Start 방어)
            recommended_artists = await self._get_fallback_artists(limit)
            reason = "최근 데뷔한 핫한 아티스트"
        else:
            # 나와 공통 팔로우가 많은 유저들이 팔로우한 다른 아티스트 추출
            artist_ids_str = ",".join(map(str, my_follows))  # 내 팔로우
            recommend_query = f"""
                SELECT f.artist_id as id
                FROM follows f
                WHERE f.user_id IN (
                    SELECT DISTINCT user_id 
                    FROM follows 
                    WHERE artist_id IN ({artist_ids_str}) AND user_id != {user_id}
                )
                AND f.artist_id NOT IN ({artist_ids_str})
                GROUP BY f.artist_id
                ORDER BY COUNT(f.user_id) DESC
                LIMIT {limit}
            """
            raw_res: list[Any] = await Artist.raw(recommend_query)
            artist_ids = [r.id for r in raw_res]

            if not artist_ids:
                # 유사 사용자가 없는 경우 기본 최신순
                recommended_artists = await self._get_fallback_artists(limit)
                reason = "최근 데뷔한 핫한 아티스트"
            else:
                # 추천된 ID들에 대해 팔로워 수 집계
                recommended_artists = await Artist.filter(id__in=artist_ids).annotate(
                    follower_count=Count("followers")
                )
                reason = "팔로우하신 아티스트와 유사한 스타일"

        result = [
            {
                "id": recs.id,
                "name": recs.stage_name,
                "profile_image": self._get_full_image_url(recs.profile_img_url),
                "company": recs.agency or "",
                "follower_count": getattr(recs, "follower_count", 0),
                "recommendation_reason": reason,
            }
            for recs in recommended_artists
        ]

        if len(result) < limit:
            needed = limit - len(result)
            # 이미 포함된 아티스트와 내 팔로우 목록 제외
            follow_ids = [int(f) for f in cast("Iterable[Any]", my_follows or [])]
            result_ids = [int(item["id"]) for item in result]

            exclude: list[int] = follow_ids + result_ids
            fallbacks = await self._get_fallback_artists(limit=needed, exclude_ids=exclude)

            result.extend(
                [
                    {
                        "id": a.id,
                        "name": a.stage_name,
                        "profile_image": a.profile_img_url or "",
                        "company": a.agency or "",
                        "follower_count": getattr(a, "follower_count", 0),
                        "recommendation_reason": "최근 데뷔한 핫한 아티스트",
                    }
                    for a in fallbacks
                ]
            )

        # 4. Redis에 저장 (1시간 유지)
        if result:
            await redis_client.setex(
                cache_key,
                3600,  # 1시간(초)
                json.dumps(result, ensure_ascii=False),
            )

        return result

    async def update_artist_profile_image(self, artist_id: int, image_file: UploadFile) -> str:
        """
        특정 아티스트의 프로필 이미지를 업로드하고 경로를 업데이트합니다.
        """
        artist = await Artist.get_or_none(id=artist_id)
        if not artist:
            raise HTTPException(status_code=404, detail="아티스트를 찾을 수 없습니다.")

        resizer = ImageResizer()
        path_prefix = f"artists/{artist_id}/profile/"

        # 기존 이미지가 있다면 S3에서 삭제
        if artist.profile_img_url:
            clean_s3_key = artist.profile_img_url
            # 상대 경로(/images/...)인 경우 프리픽스 제거 후 삭제
            if clean_s3_key.startswith("/images/"):
                clean_s3_key = clean_s3_key.replace("/images/", "", 1)
            # 전체 URL(https://...)인 경우 S3 키만 추출하여 삭제
            elif clean_s3_key.startswith("https://"):
                clean_s3_key = urlparse(clean_s3_key).path.lstrip("/")
                # 만약 전체 URL 경로에도 /images/가 포함되어 있다면 제거
                if clean_s3_key.startswith("images/"):
                    clean_s3_key = clean_s3_key.replace("images/", "", 1)

            await resizer.delete_all_by_id_path(clean_s3_key)

        # 새 이미지 리사이징 및 업로드 (400px 기준)
        uploaded_urls = await resizer.upload_square_resizes(
            image_file=image_file.file, sizes=(400,), path_prefix=path_prefix
        )

        if "400" not in uploaded_urls:
            raise HTTPException(status_code=500, detail="이미지 업로드에 실패했습니다.")

        # DB 저장용 경로 생성 (/images/ 프리픽스 추가)
        s3_url = uploaded_urls["400"]
        pure_path = urlparse(s3_url).path.lstrip("/")
        db_path = f"/images/{pure_path}"

        # DB 업데이트
        artist.profile_img_url = db_path
        await artist.save(update_fields=["profile_img_url"])

        return self._get_full_image_url(db_path)


artist_service = ArtistService()
