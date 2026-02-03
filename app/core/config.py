import base64
import contextlib
import os
import time
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# fastadmin 등에서 os.environ을 직접 읽으므로 .env를 먼저 로드
ENV_FILE = f"envs/.{os.getenv('MODE', 'local')}.env"
load_dotenv(ENV_FILE, override=False)

# 시스템 타임존 설정
os.environ["TZ"] = "Asia/Seoul"
with contextlib.suppress(AttributeError):
    time.tzset()

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    return datetime.now(KST)


class Settings(BaseSettings):
    # api 버전경로 명시
    API_V1_STR: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=f"envs/.{os.getenv('MODE', 'local')}.env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 기본 설정
    MODE: str = Field(default="local")

    # DB 설정
    DB_SCHEME: str
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str

    # REDIS 설정
    REDIS_HOST: str
    REDIS_PORT: str

    AUTO_SCHEMA: str = "0"  # 개발 초기에만 1로 켜서 generate_schemas를 쓰는 경우에 사용

    # 보안 설정
    SECRET_KEY: str
    STREAM_KEY_ENCRYPTION_KEY: str  # IVS 키 암호화용
    ADMIN_SECRET_KEY: str  # FastAPI Admin용
    ACCESS_TOKEN_EXPIRE_MINUTES: int  # 토큰 유효분
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 리프레시 토큰 유효일

    # CORS 설정
    CORS_ORIGINS: list[str] = []

    # ADMIN 계정
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str

    # AWS IVS, S3
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "ap-northeast-2"
    IVS_PLAYBACK_PRIVATE_KEY_B64: str = Field(..., validation_alias="IVS_PLAYBACK_PRIVATE_KEY_B64")
    S3_RECORDING_BUCKET: str
    IMAGES_BUCKET: str
    IVS_WEBHOOK_SECRET: str
    ADMIN_IVS_PLAYBACK_TOKEN_EXPIRATION_SEC: int = 600  # 10 min
    IVS_PLAYBACK_TOKEN_EXPIRATION_SEC: int = 3600  # 60 min

    # AWS COGNITO
    COGNITO_CLIENT_ID: str
    COGNITO_CLIENT_SECRET: str
    COGNITO_DOMAIN: str
    COGNITO_USER_POOL_ID: str
    COGNITO_REDIRECT_URI: str

    # social_login
    NAVER_REDIRECT_URI: str
    NAVER_CLIENT_ID: str
    NAVER_CLIENT_SECRET: str

    CALLBACK_REDIRECT_URL: str

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        return f"{self.DB_SCHEME}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    @property
    def IVS_PLAYBACK_PRIVATE_KEY(self) -> str:
        """Base64로 저장된 키를 원본 PEM 문자열로 디코딩"""
        try:
            return base64.b64decode(self.IVS_PLAYBACK_PRIVATE_KEY_B64).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"IVS PRIVATE KEY 디코딩 실패: {e}") from e

    @property
    def COGNITO_JWKS_URL(self) -> str:
        return f"https://cognito-idp.{self.AWS_REGION}.amazonaws.com/{self.COGNITO_USER_POOL_ID}/.well-known/jwks.json"


settings = Settings()

print(
    "\n\n"
    + "=" * 50
    + f"\n      Running in [{settings.MODE}] mode (DB: {settings.DB_HOST})\n"
    + "=" * 50
    + "\n\n"
)
