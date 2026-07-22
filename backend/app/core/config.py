from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Discrete fields — used for self-hosted Postgres (dev, or the VPS path)
    # where there's no single connection string to hand around. Optional
    # (not required) because a Neon-style deploy sets DATABASE_URL instead
    # and never touches these; see database_url below for how the two combine.
    postgres_user: str = ""
    postgres_password: str = ""
    postgres_db: str = ""
    # Container-to-container traffic always uses Postgres's own port (5432),
    # not POSTGRES_PORT (that only maps the port for connections from the host).
    postgres_host: str = "postgres"
    postgres_internal_port: int = 5432

    # Set by Neon (or any managed Postgres that hands out one connection
    # string) — takes priority over the discrete fields above when present.
    # Needs an explicit alias: the property below is already named
    # `database_url`, so without this, pydantic-settings would map this field
    # to env var DATABASE_URL_RAW (its own uppercased name), not the
    # DATABASE_URL every managed Postgres provider actually sets.
    database_url_raw: str | None = Field(default=None, alias="DATABASE_URL")

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Object storage — Supabase Storage's S3-compatible API in every
    # environment now (no more self-hosted MinIO container anywhere,
    # including dev; see backend/MIGRATION.md). storage_endpoint is the full
    # URL Supabase gives you (includes a path, e.g. .../storage/v1/s3), not
    # just a host:port — that's *why* this uses boto3 rather than the `minio`
    # package, whose endpoint parameter only accepts a bare hostname.
    storage_endpoint: str
    storage_region: str
    storage_access_key: str
    storage_secret_key: str
    storage_bucket_name: str = "documents"

    # Embedding provider. embedding_dim is authoritative for the Qdrant
    # collection size (vector_store reads it via the provider, not this field
    # directly) — change it together with embedding_model, never alone, or
    # vector_store's dimension-mismatch check will recreate every collection
    # for no reason.
    gemini_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768

    # Discrete host/port — self-hosted Qdrant (dev, or the VPS path), no auth.
    qdrant_host: str = "qdrant"
    qdrant_internal_port: int = 6333
    # Set for Qdrant Cloud — a full URL (e.g.
    # https://xxxx.aws.cloud.qdrant.io), takes priority over qdrant_host/
    # qdrant_internal_port above when present. qdrant_api_key is required
    # alongside it; Qdrant Cloud rejects unauthenticated requests.
    qdrant_url: str | None = None
    qdrant_api_key: str = ""

    openrouter_api_key: str = ""
    # Change LLM_MODEL in .env to try other OpenRouter models. Default is a
    # free-tier model to avoid unexpected cost.
    llm_model: str = "openai/gpt-oss-20b:free"

    # Comma-separated list, e.g. "https://your-app.vercel.app,http://localhost:5173".
    # "*" (the default) is fine for local dev only — a split-origin deploy
    # (Vercel frontend, Render backend) needs the real Vercel origin here, or
    # every browser request the frontend makes gets blocked by CORS.
    cors_allowed_origins: str = "*"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def database_url(self) -> str:
        if self.database_url_raw:
            return self.database_url_raw
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_internal_port}/{self.postgres_db}"
        )


settings = Settings()
