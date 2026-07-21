# Import each model module here so Base.metadata sees all tables
# (required for Alembic autogenerate to detect them).
from app.models.organization import Organization  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.collection import Collection  # noqa: F401
