from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    KAFKA_BOOTSTRAP_SERVERS: str
    APP_NAME: str
    DEBUG: bool

    class Config:
        env_file = ".env"


settings = Settings()

