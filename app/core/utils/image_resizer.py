from __future__ import annotations

import io
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException, status
from PIL import Image, ImageOps

from app.integrations.s3_client import S3Client

logger = logging.getLogger(__name__)


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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="유효한 이미지 파일이 아닙니다.",
            ) from exc

        base_prefix = path_prefix.rstrip("/")

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

                key = f"{base_prefix}/image_{size}.png"

                # 비동기 업로드 호출
                await self.s3_client.upload_with_key(
                    buffer,
                    key=key,
                    extra_args={"ContentType": "image/png"},
                )

                urls[str(size)] = self.s3_client.build_url(key)

            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="이미지 리사이징 또는 업로드에 실패했습니다.",
                ) from exc

        return urls

    async def delete_all_by_id_path(self, image_url: str | None) -> None:
        """
        URL에서 폴더 경로를 추출하여 해당 폴더 내의 모든 파일을 삭제합니다.
        보안을 위해 지정한 경로 패턴(users/{id}/profile 등)만 허용합니다.
        """
        if not image_url:
            return

        try:
            parsed_url = urlparse(image_url)
            full_path = parsed_url.path.lstrip("/")
            folder_prefix = os.path.dirname(full_path)  # ex: "users/1/profile"

            # users/{숫자}/profile 등의 패턴인지 확인
            allowed_patterns = [
                r"^users/\d+/profile$",
                r"^artists/\d+/profile$",
                r"^concerts/\d+/thumbnail$",
            ]
            if not any(re.match(pattern, folder_prefix) for pattern in allowed_patterns):
                logger.warning(f"S3 삭제 거부: 허용되지 않은 경로 접근 ({folder_prefix})")
                return

            await self.s3_client.delete_prefix(prefix=folder_prefix)
            logger.info(f"S3 이미지 폴더 삭제 완료: {folder_prefix}")

        except Exception as e:
            logger.error(f"S3 삭제 도중 에러 발생: {e}", exc_info=True)
