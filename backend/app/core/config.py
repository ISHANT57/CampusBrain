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

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_internal_port}/{self.postgres_db}"
        )


settings = Settings()
