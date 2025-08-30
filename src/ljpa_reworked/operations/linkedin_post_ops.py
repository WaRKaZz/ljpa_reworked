from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from ljpa_reworked.models.database_models import LinkedinPost


def create_linkedin_post(
    db: Session,
    text: str | None = None,
    screenshot_path: str | None = None,
    url: str | None = None,
) -> LinkedinPost:
    """Create a new LinkedIn post record."""
    post = LinkedinPost(
        text=text,
        screenshot_path=screenshot_path,
        url=url,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


def get_linkedin_post_by_id(db: Session, post_id: int) -> LinkedinPost | None:
    """Get a LinkedIn post by its ID, excluding soft-deleted ones."""
    return (
        db.query(LinkedinPost)
        .filter(and_(LinkedinPost.id == post_id, LinkedinPost.deleted.is_(False)))
        .first()
    )


def get_linkedin_posts_by_vacancy(db: Session, vacancy_id: int) -> list[LinkedinPost]:
    """Get all non-deleted LinkedIn posts for a specific vacancy."""
    return (
        db.query(LinkedinPost)
        .filter(
            and_(LinkedinPost.vacancy_id == vacancy_id, LinkedinPost.deleted.is_(False))
        )
        .all()
    )


def get_unprocessed_linkedin_posts(db: Session) -> list[LinkedinPost]:
    """Get all unprocessed and not deleted LinkedIn posts."""
    return (
        db.query(LinkedinPost)
        .filter(
            and_(LinkedinPost.processed.is_(False), LinkedinPost.deleted.is_(False))
        )
        .all()
    )


def get_all_linkedin_posts(
    db: Session, skip: int = 0, limit: int = 100
) -> list[LinkedinPost]:
    """Get all non-deleted LinkedIn posts, sorted by most recent first."""
    return (
        db.query(LinkedinPost)
        .filter(LinkedinPost.deleted.is_(False))
        .order_by(desc(LinkedinPost.id))
        .offset(skip)
        .limit(limit)
        .all()
    )


def mark_linkedin_post_as_processed(db: Session, post_id: int) -> LinkedinPost | None:
    """Mark a LinkedIn post as processed."""
    post = get_linkedin_post_by_id(db, post_id)
    if post:
        post.processed = True
        db.commit()
        db.refresh(post)
    return post


def update_linkedin_post(db: Session, post_id: int, **kwargs) -> LinkedinPost | None:
    """Update LinkedIn post fields."""
    post = get_linkedin_post_by_id(db, post_id)
    if post:
        for key, value in kwargs.items():
            if hasattr(post, key):
                setattr(post, key, value)
        db.commit()
        db.refresh(post)
    return post


def link_post_to_vacancy(
    db: Session, post_id: int, vacancy_id: int
) -> LinkedinPost | None:
    """Link a LinkedIn post to a vacancy by their IDs."""
    # A more robust implementation could also check if the vacancy_id is valid
    # by fetching the Vacancy object first.
    post = get_linkedin_post_by_id(db, post_id)
    if post:
        post.vacancy_id = vacancy_id
        db.commit()
        db.refresh(post)
    return post


def soft_delete_linkedin_post(db: Session, post_id: int) -> bool:
    """Soft delete a LinkedIn post."""
    post = db.query(LinkedinPost).filter(LinkedinPost.id == post_id).first()
    if post:
        post.deleted = True
        db.commit()
        return True
    return False


def search_linkedin_posts_by_text(db: Session, keyword: str) -> list[LinkedinPost]:
    """Search non-deleted LinkedIn posts by text content."""
    return (
        db.query(LinkedinPost)
        .filter(
            and_(LinkedinPost.text.contains(keyword), LinkedinPost.deleted.is_(False))
        )
        .all()
    )


def get_duplicate_post(db: Session, text: str, threshold: int) -> LinkedinPost | None:
    """Check if a vacancy with similar text exists."""
    from thefuzz import fuzz

    vacancies = db.query(LinkedinPost).filter(LinkedinPost.deleted.is_(False)).all()
    for vacancy in vacancies:
        similarity = fuzz.token_set_ratio(vacancy.text, text)
        if similarity >= threshold:
            return vacancy
    return None
