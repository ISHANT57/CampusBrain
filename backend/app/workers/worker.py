from arq.connections import RedisSettings

from app.core.config import settings
from app.workers.tasks import sleep_and_log


class WorkerSettings:
    functions = [sleep_and_log]
    redis_settings = RedisSettings(host=settings.redis_host, port=settings.redis_internal_port)
