import enum
from datetime import datetime
from typing import Annotated, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ljpa_reworked.database import Base

from .crewai_pydantic_models import VisaStatus
from .enums import VacancyStatus

created_at = Annotated[
    datetime, mapped_column(DateTime(timezone=False), server_default=func.now())
]

updated_at = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=datetime.utcnow
    ),
]


class DataSource(enum.Enum):
    linkedin = "LinkedIn"
    other = "other"


class Vacancy(Base):
    __tablename__ = "vacancy"
    __table_args__ = (
        CheckConstraint(
            "(submit_email IS NOT NULL AND TRIM(submit_email) != '') OR (submit_url IS NOT NULL AND TRIM(submit_url) != '')",
            name="check_vacancy_has_contact_method",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    submit_email: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submit_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, unique=True
    )
    source: Mapped[DataSource] = mapped_column(
        Enum(
            DataSource,
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,
        ),
        nullable=False,
    )
    visa_status: Mapped[VisaStatus] = mapped_column(
        Enum(
            VisaStatus,
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,
        ),
        nullable=False,
    )
    created_at: Mapped[created_at]
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(VacancyStatus, name="vacancystatus", native_enum=False),
        default=VacancyStatus.created,
        server_default=VacancyStatus.created.value,
        nullable=False,
    )
    applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Relationships
    basic_evaluation: Mapped[Optional["BasicEvaluation"]] = relationship(
        back_populates="vacancy"
    )
    telegram_status: Mapped[Optional["TelegramStatus"]] = relationship(
        back_populates="vacancy"
    )
    resumes: Mapped[list["Resume"]] = relationship(back_populates="vacancy")
    emails: Mapped[list["Email"]] = relationship(back_populates="vacancy")


class BasicEvaluation(Base):
    __tablename__ = "basic_evaluation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancy.id"))
    created_at: Mapped[created_at]

    @validates("rating")
    def validate_rating(self, key, rating):
        if rating < 0 or rating > 100:
            raise ValueError("Rating must be between 0 and 100")
        return rating

    # Relationship
    vacancy: Mapped["Vacancy"] = relationship(back_populates="basic_evaluation")


class TelegramStatus(Base):
    __tablename__ = "telegram_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancy.id"))

    # Relationship
    vacancy: Mapped["Vacancy"] = relationship(back_populates="telegram_status")


class Resume(Base):
    __tablename__ = "resume"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fullname: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=False)
    personal_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    education: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    experience: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    certifications: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    skills: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    projects: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancy.id"))
    created_at: Mapped[created_at]
    rendered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    # Relationship
    vacancy: Mapped["Vacancy"] = relationship(back_populates="resumes")


class Email(Base):
    __tablename__ = "email"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipient: Mapped[str] = mapped_column(String(100))
    resume_path: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    vacancy_id: Mapped[int] = mapped_column(Integer, ForeignKey("vacancy.id"))
    created_at: Mapped[created_at]
    # Relationship
    vacancy: Mapped["Vacancy"] = relationship(back_populates="emails")
