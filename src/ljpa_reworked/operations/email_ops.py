from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import EmailCrewAI
from ljpa_reworked.models.database_models import Email


def create_email(
    db: Session,
    vacancy_id: int,
    email_data: EmailCrewAI,
    recipient: str,
    resume_path: str | None = None,  # <-- Fixed type and name
) -> Email:
    """Create email for vacancy application"""
    email = Email(
        vacancy_id=vacancy_id,
        subject=email_data.subject,
        body=email_data.body,
        recipient=recipient,
        resume_path=resume_path,  # <-- Fixed assignment
    )
    db.add(email)
    db.commit()
    db.refresh(email)
    return email


def get_email_by_id(db: Session, email_id: int) -> Email | None:
    """Get email by ID"""
    return db.query(Email).filter(Email.id == email_id).first()


def get_emails_by_vacancy(db: Session, vacancy_id: int) -> list[Email]:
    """Get all emails for specific vacancy"""
    return db.query(Email).filter(Email.vacancy_id == vacancy_id).all()


def get_pending_emails(db: Session) -> list[Email]:
    """Get emails that haven't been sent yet"""
    return db.query(Email).filter(Email.sent.is_(False)).all()


def get_sent_emails(db: Session) -> list[Email]:
    """Get all sent emails"""
    return db.query(Email).filter(Email.sent.is_(True)).all()


def mark_email_sent(db: Session, email_id: int) -> bool:
    """Mark email as sent"""
    email = get_email_by_id(db, email_id)
    if email:
        email.sent = True
        db.commit()
        return True
    return False


def get_emails_by_recipient(db: Session, recipient: str) -> list[Email]:
    """Get all emails sent to specific recipient"""
    return db.query(Email).filter(Email.recipient == recipient).all()


def search_emails_by_subject(db: Session, keyword: str) -> list[Email]:
    """Search emails by subject"""
    return db.query(Email).filter(Email.subject.contains(keyword)).all()


def update_email(db: Session, email_id: int, **kwargs) -> Email | None:
    """Update email fields"""
    email = get_email_by_id(db, email_id)
    if email:
        for key, value in kwargs.items():
            if hasattr(email, key):
                setattr(email, key, value)
        db.commit()
        db.refresh(email)
    return email


def delete_email(db: Session, email_id: int) -> bool:
    """Delete email"""
    email = get_email_by_id(db, email_id)
    if email:
        db.delete(email)
        db.commit()
        return True
    return False
