from __future__ import annotations

import io
import os
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status
from PIL import Image, ImageOps

from app.core.utils.s3_client import S3Client


class ImageResizer:
    def __init__(self, s3_client: S3Client | None = None) -> None:
        self.s3_client = s3_client or S3Client()

    async def upload_square_resizes(
        self,
        *,
        image_file: Any,
        sizes: tuple[int, ...],
        path_prefix: str,
    ) -> dict[str, str]:
        urls: dict[str, str] = {}
        try:
            source = Image.open(image_file)
            source.load()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="이미지 처리에 실패했습니다.",
            ) from exc

        for size in sizes:
            try:
                # 리사이징 작업 (CPU 집중 작업이므로 대량 처리 시 run_in_threadpool 고려 가능)
                resized = ImageOps.fit(
                    source,
                    (size, size),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                buffer = io.BytesIO()
                buffer.name = f"image_{size}.png"
                resized.save(buffer, format="PNG")
                buffer.seek(0)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="이미지 리사이징에 실패했습니다.",
                ) from exc

            base_prefix = path_prefix.rstrip("/")
            # 비동기 업로드 호출
            key = await self.s3_client.upload_with_key(
                buffer,
                key=f"{base_prefix}/profile{size}.png",
                extra_args={"ContentType": "image/png"},
            )
            urls[str(size)] = self.s3_client.build_url(key)
        return urls

    async def delete_all_by_id_path(self, image_url: str | None) -> None:
        """
        URL에서 폴더 경로를 추출하여 해당 폴더 내의 모든 파일을 삭제합니다.
        보안을 위해 유저 프로필 경로 패턴(users/{id}/profile)만 허용합니다.
        """
        if not image_url:
            return

        try:
            parsed_url = urlparse(image_url)
            full_path = parsed_url.path.lstrip("/")
            folder_prefix = os.path.dirname(full_path)  # ex: "users/1/profile"

            # users/{숫자}/profile 패턴인지 확인
            profile_path_pattern = r"^users/\d+/profile$"
            if not re.match(profile_path_pattern, folder_prefix):
                print(f"S3 삭제 거부: 허용되지 않은 경로 접근 ({folder_prefix})")
                return

            if folder_prefix:
                await self.s3_client.delete_prefix(prefix=folder_prefix)
                print(f"S3 이미지 폴더 삭제 완료: {folder_prefix}")

        except Exception as e:
            print(f"S3 삭제 도중 에러 발생: {e}")
