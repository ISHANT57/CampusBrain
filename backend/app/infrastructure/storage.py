# pyrefly: ignore [missing-import]
import boto3
# pyrefly: ignore [missing-import]
from botocore.config import Config
# pyrefly: ignore [missing-import]
from botocore.exceptions import ClientError

from app.core.config import settings

# boto3, not the `minio` package that was here before: Supabase's S3-compatible
# endpoint includes a path (.../storage/v1/s3), and minio-py's `endpoint`
# parameter only ever accepts a bare hostname or host:port (confirmed against
# its own docs — every example is `s3.amazonaws.com`, `server:9000`, etc.,
# never a URL with a path). It has no field to carry that path. boto3's
# endpoint_url takes a full URL, so it's the one that actually works here —
# and unchanged, it still works fine against self-hosted MinIO too, so this
# isn't a Supabase-only special case if that's ever needed again.
_client = boto3.client(
    "s3",
    endpoint_url=settings.storage_endpoint,
    region_name=settings.storage_region,
    aws_access_key_id=settings.storage_access_key,
    aws_secret_access_key=settings.storage_secret_key,
    config=Config(
        # Path-style keeps the bucket name in the URL path
        # (.../storage/v1/s3/documents/...) instead of boto3's default of
        # prepending it as a subdomain (documents.<ref>.storage.supabase.co) —
        # the latter can't resolve against a path-suffixed endpoint.
        s3={"addressing_style": "path"},
        signature_version="s3v4",
    ),
)


def _ensure_bucket() -> None:
    """Best-effort only — never raises. The bucket is created once, out of
    band, in the Supabase dashboard (Storage → New bucket, kept Private);
    this just confirms it's reachable. Managed S3 services commonly disallow
    CreateBucket over the S3 API itself, and different failure modes (missing
    bucket vs. no permission to check vs. a transient network blip) shouldn't
    all crash app startup the same way arbitrary infra hiccups would if this
    were allowed to raise — a slow storage provider on one boot shouldn't take
    the whole API down before it can even serve /health.
    """
    try:
        _client.head_bucket(Bucket=settings.storage_bucket_name)
    except Exception as e:
        print(
            f"[storage] could not confirm bucket '{settings.storage_bucket_name}' exists "
            f"at startup ({e}); continuing — create it in the Supabase dashboard if uploads "
            "start failing."
        )


_ensure_bucket()


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client.put_object(Bucket=settings.storage_bucket_name, Key=key, Body=data, ContentType=content_type)


def get_object(key: str) -> bytes:
    response = _client.get_object(Bucket=settings.storage_bucket_name, Key=key)
    return response["Body"].read()


def delete_object(key: str) -> None:
    _client.delete_object(Bucket=settings.storage_bucket_name, Key=key)


def object_exists(key: str) -> bool:
    try:
        _client.head_object(Bucket=settings.storage_bucket_name, Key=key)
        return True
    except ClientError:
        return False


def presigned_url(key: str, expires_in: int = 3600) -> str:
    """A time-limited URL for downloading one object without exposing the
    storage credentials to whoever the link is shared with. Bucket stays
    Private; this is the sanctioned way to hand out temporary access to a
    single object in it."""
    return _client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.storage_bucket_name, "Key": key},
        ExpiresIn=expires_in,
    )


def health_check() -> tuple[bool, str]:
    """Used by GET /health/storage — a real connectivity check, deliberately
    kept out of the plain /health liveness probe (see main.py's comment on
    that route) so a storage blip doesn't get the whole process restarted."""
    try:
        _client.head_bucket(Bucket=settings.storage_bucket_name)
        return True, "reachable"
    except Exception as e:
        return False, str(e)
