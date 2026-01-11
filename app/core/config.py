from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str

    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str
    DB_SCHEME: str

settings = Settings() # type: ignore[call-arg]