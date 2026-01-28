import logging
import uuid
from typing import Any, cast

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Client:
    def __init__(self) -> None:
        self.session = aioboto3.Session()
        self.bucket_name = settings.S3_RECORDING_BUCKET
        self.aws_config = {
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "region_name": settings.AWS_REGION,
        }

    async def upload(
        self, file: Any, path_prefix: str = "", extra_args: dict[str, Any] | None = None
    ) -> str:
        original_name = getattr(file, "name", "unknown_file")
        ext = original_name.split(".")[-1] if "." in original_name else "bin"

        file_name = f"{uuid.uuid4()}.{ext}"

        clean_prefix = path_prefix.rstrip("/")
        key = f"{clean_prefix}/{file_name}" if clean_prefix else file_name
        key = key.lstrip("/")

        upload_params: dict[str, Any] = extra_args.copy() if extra_args else {}

        if "ContentType" not in upload_params:
            content_type = getattr(file, "content_type", None)
            if content_type:
                upload_params["ContentType"] = content_type

        try:
            async with self.session.client("s3", **self.aws_config) as s3:
                await s3.upload_fileobj(file, self.bucket_name, key, ExtraArgs=upload_params)
            return key
        except ClientError as e:
            logger.error(f"S3 Upload Failed: {e}", exc_info=True)
            raise e

    async def upload_with_key(
        self, file_obj: Any, key: str, extra_args: dict[str, Any] | None = None
    ) -> str:
        """지정된 Key로 파일을 업로드 (TypeError 방지를 위해 put_object 사용)"""
        upload_params: dict[str, Any] = extra_args.copy() if extra_args else {}

        # extra_args에서 ContentType 추출 및 제거 (put_object 파라미터와 겹치지 않게 함)
        content_type = upload_params.pop("ContentType", "application/octet-stream")

        try:
            # file_obj가 BytesIO 객체인 경우 데이터를 읽어옴
            if hasattr(file_obj, "read"):
                body = file_obj.read()
                # 만약 커서가 끝에 있다면 다시 앞으로 돌려줌
                if not body and hasattr(file_obj, "seek"):
                    file_obj.seek(0)
                    body = file_obj.read()
            else:
                body = file_obj

            async with self.session.client("s3", **self.aws_config) as s3:
                # upload_fileobj 대신 put_object를 사용하여 asyncio 충돌 회피
                await s3.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=body,
                    ContentType=content_type,
                    **upload_params,
                )
            return key
        except Exception as e:
            logger.error(f"S3 Upload With Key Failed: {e}", exc_info=True)
            raise e

    async def delete_object(self, key: str) -> None:
        try:
            async with self.session.client("s3", **self.aws_config) as s3:
                await s3.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            logger.warning(f"S3 Delete Failed (Key: {key}): {e}", exc_info=True)

    async def delete_prefix(self, prefix: str) -> None:
        """특정 경로(prefix)로 시작하는 모든 객체를 삭제"""
        async with self.session.client("s3", **self.aws_config) as s3:
            objects_to_delete = await s3.list_objects_v2(Bucket=self.bucket_name, Prefix=prefix)

            if "Contents" in objects_to_delete:
                delete_keys: Any = [{"Key": obj["Key"]} for obj in objects_to_delete["Contents"]]
                await s3.delete_objects(Bucket=self.bucket_name, Delete={"Objects": delete_keys})

    def build_url(self, key: str) -> str:
        if not key:
            return ""

        return (
            f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{key.lstrip('/')}"
        )

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            async with self.session.client("s3", **self.aws_config) as s3:
                url = await s3.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={
                        "Bucket": self.bucket_name,
                        "Key": key,
                    },
                    ExpiresIn=expires_in,
                )
            return cast("str", url)
        except ClientError as e:
            logger.error(f"S3 Presigned URL Generation Failed: {e}", exc_info=True)
            return str(e)
