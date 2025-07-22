from datetime import datetime

from sqlalchemy.orm import Session, joinedload

from ljpa_reworked.models.database_models import TelegramStatus, Vacancy


def mark_vacancy_as_sent(db: Session, vacancy_id: int) -> TelegramStatus:
    """
    Marks a vacancy as sent via Telegram. If a TelegramStatus record
    exists, it's updated. Otherwise, a new one is created.

    Args:
        db: The database session.
        vacancy_id: The ID of the vacancy.

    Returns:
        The TelegramStatus object for the vacancy.

    Raises:
        ValueError: If the vacancy with the given ID is not found.
    """
    vacancy = (
        db.query(Vacancy)
        .options(joinedload(Vacancy.telegram_status))
        .filter(Vacancy.id == vacancy_id)
        .one_or_none()
    )

    if not vacancy:
        raise ValueError(f"Vacancy with ID {vacancy_id} not found.")

    if vacancy.telegram_status:
        vacancy.telegram_status.sent = True
        vacancy.telegram_status.date = datetime.utcnow()
        status = vacancy.telegram_status
    else:
        status = TelegramStatus(sent=True, vacancy_id=vacancy_id)
        db.add(status)

    db.commit()
    db.refresh(status)

    return status
