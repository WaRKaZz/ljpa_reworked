import enum
from datetime import datetime
from typing import Annotated, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ljpa_reworked.database import Base

from .crewai_pydantic_models import VisaStatus

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    credentials: Mapped[str | None] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(200), nullable=True)
    source: Mapped[DataSource]
    visa_status: Mapped[VisaStatus]
    created_at: Mapped[created_at]
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

    # Relationships
    basic_evaluation: Mapped[Optional["BasicEvaluation"]] = relationship(
        back_populates="vacancy"
    )
    linkedin_posts: Mapped[Optional["LinkedinPost"]] = relationship(
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


class LinkedinPost(Base):
    __tablename__ = "linkedin_post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[created_at]
    vacancy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vacancy.id"), nullable=True
    )
    created_at: Mapped[created_at]
    # Relationship
    vacancy: Mapped["Vacancy"] = relationship(back_populates="linkedin_posts")


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
