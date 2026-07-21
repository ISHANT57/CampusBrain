from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    postgres_user: str
    postgres_password: str
    postgres_db: str
    # Container-to-container traffic always uses Postgres's own port (5432),
    # not POSTGRES_PORT (that only maps the port for connections from the host).
    postgres_host: str = "postgres"
    postgres_internal_port: int = 5432

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    minio_root_user: str
    minio_root_password: str
    minio_host: str = "minio"
    minio_internal_port: int = 9000
    minio_bucket_name: str = "documents"

    redis_host: str = "redis"
    redis_internal_port: int = 6379

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_internal_port}/{self.postgres_db}"
        )

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_internal_port}"


settings = Settings()
