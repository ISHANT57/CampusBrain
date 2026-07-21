# Throwaway model to prove the Alembic round-trip (M6 DoD).
# Deleted, along with its migration, once upgrade/downgrade is verified.
from sqlalchemy import Column, Integer, String

from app.core.database import Base


class SmokeTest(Base):
    __tablename__ = "_smoke_test"

    id = Column(Integer, primary_key=True)
    note = Column(String, nullable=False)
