"""Request correlation and structured logging.

The request id lives in a ContextVar rather than being threaded through every
call signature: it is ambient request state that no business function needs
to know about, and passing it explicitly would touch rag_service,
retrieval_service and vector_store to carry a value none of them use.

ContextVar (not threading.local) because FastAPI runs async endpoints on an
event loop and sync ones in a threadpool; ContextVar is correct under both,
and copy_context() means a value set in the middleware is visible inside a
BackgroundTask spawned from the same request.
"""

import contextvars
import json
import logging

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# Same ambient-state argument as request_id: these are set once, by whichever
# auth dependency resolved the caller, and read only by the http_request log
# line in main.py. Threading them through every endpoint signature would
# couple layers to values none of them use.
#
# int | None rather than a sentinel: anonymous chat genuinely has no user
# (ADR-008) and a service API key genuinely has no user row, so "absent" is
# a real, meaningful value here -- not a missing one.
tenant_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("tenant_id", default=None)
user_id_var: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)


class RequestIdFilter(logging.Filter):
    """Inject the current request id into every record.

    A Filter rather than a custom Logger: this way third-party libraries' log
    records -- and main.py's existing logging.exception on the 500 path --
    pick up the id without any of them knowing it exists.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line, to stdout.

    stdout, never a file: Render's filesystem is ephemeral with no persistent
    disk, so a log file is deleted on every deploy and invisible to the
    platform's log stream.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        # Anything passed as logger.info("...", extra={"event": {...}}) is
        # merged in flat, so queries filter on top-level keys.
        if hasattr(record, "event"):
            payload.update(record.event)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # json.dumps, not string interpolation: this is what makes a
        # newline inside request_id (client-supplied) land inside a JSON
        # string value instead of splitting the line -- log injection is
        # structurally impossible here, not merely avoided by convention.
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()  # uvicorn installs its own; replace it
    root.addHandler(handler)
    root.setLevel(level)
