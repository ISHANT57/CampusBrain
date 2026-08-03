# Import each model module here so Base.metadata sees all tables
# (required for Alembic autogenerate to detect them).
from app.models.organization import Organization  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.collection import Collection  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.chunk import Chunk  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.ingestion_job import IngestionJob  # noqa: F401
from app.models.usage_log import UsageLog  # noqa: F401
