from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.core.config import settings

_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_root_user,
    secret_key=settings.minio_root_password,
    secure=False,
)


def _ensure_bucket() -> None:
    if not _client.bucket_exists(settings.minio_bucket_name):
        _client.make_bucket(settings.minio_bucket_name)


_ensure_bucket()


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    _client.put_object(settings.minio_bucket_name, key, BytesIO(data), length=len(data), content_type=content_type)


def get_object(key: str) -> bytes:
    response = _client.get_object(settings.minio_bucket_name, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_object(key: str) -> None:
    _client.remove_object(settings.minio_bucket_name, key)


def object_exists(key: str) -> bool:
    try:
        _client.stat_object(settings.minio_bucket_name, key)
        return True
    except S3Error:
        return False
