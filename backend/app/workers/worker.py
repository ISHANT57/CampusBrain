from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.tasks import process_document


class WorkerSettings:
    functions = [process_document]
    redis_settings = RedisSettings(host=settings.redis_host, port=settings.redis_internal_port)
