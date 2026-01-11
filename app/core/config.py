"""pydantic-settings 기반 설정.

여기에 넣을 것:
- env 파일 로딩(예: envs/.local.env)
- DB 설정, SECRET_KEY, 외부 API 키(Kakao/Naver), AWS 설정 등
- DB URL 조합 프로퍼티(DATABASE_URL)

주의:
- 필수 필드를 너무 많이 만들어두면 테스트/CI에서 env 없어서 터질 수 있음.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="envs/.local.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DB_SCHEME: str = "postgres"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "near05_db"
    DB_USER: str = "db"
    DB_PASSWORD: str = "pw1234"

    AUTO_SCHEMA: str = "0"  # 개발 초기에만 1로 켜서 generate_schemas를 쓰는 경우에 사용

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"{self.DB_SCHEME}://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
