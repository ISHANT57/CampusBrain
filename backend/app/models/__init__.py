# Import each model module here so Base.metadata sees all tables
# (required for Alembic autogenerate to detect them).
from app.models._smoke_test import SmokeTest  # noqa: F401
