from typing import Annotated

from sqlalchemy import String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from ljpa_reworked.config import DATABASE_URL

# Create engine for SQLite
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

str_256 = Annotated[str, 256]


# Create base class for models
class Base(DeclarativeBase):
    type_annotation_map = {str_256: String(256)}

    repr_cols_num = 3
    repr_cols = ()

    def __repr__(self):
        """Relationships не используются в repr(), т.к. могут вести к неожиданным подгрузкам."""
        cols = []
        for idx, col in enumerate(self.__table__.columns.keys()):
            if col in self.repr_cols or idx < self.repr_cols_num:
                cols.append(f"{col}={getattr(self, col)}")

        return f"<{self.__class__.__name__} {', '.join(cols)}>"

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


def init_db(bind_engine=None) -> None:
    """Initialize SQLite database schema directly using SQLAlchemy metadata."""
    if bind_engine is None:
        bind_engine = engine
    import ljpa_reworked.models.database_models  # noqa: F401

    Base.metadata.create_all(bind=bind_engine)
    with bind_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_resume_vacancy_id ON resume (vacancy_id)"
            )
        )
        try:
            connection.execute(
                text(
                    "ALTER TABLE basic_evaluation ADD COLUMN visa_probability INTEGER DEFAULT 100 NOT NULL"
                )
            )
        except Exception:
            pass
