from sqlalchemy.orm import Session

from ljpa_reworked.models.crewai_pydantic_models import ResumeCrewAI
from ljpa_reworked.models.database_models import Resume


def create_resume(
    db: Session, vacancy_id: int, resume_data: ResumeCrewAI, path: str | None = None
) -> Resume:
    """Create resume for specific vacancy"""
    personal_info = resume_data.personal_info

    resume = Resume(
        vacancy_id=vacancy_id,
        fullname=personal_info.name,
        email=personal_info.email,
        phone=personal_info.phone,
        address=personal_info.address,
        summary=resume_data.summary,
        personal_info=personal_info.model_dump(),
        education=[edu.model_dump() for edu in resume_data.education],
        experience=[exp.model_dump() for exp in resume_data.experience],
        skills=[skill.model_dump() for skill in resume_data.skills],
        projects=[proj.model_dump() for proj in resume_data.projects],
        certifications=[cert.model_dump() for cert in resume_data.certifications],
        path=path,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_resume_by_id(db: Session, resume_id: int) -> Resume | None:
    """Get resume by ID"""
    return db.query(Resume).filter(Resume.id == resume_id).first()


def get_resume_by_vacancy(db: Session, vacancy_id: int) -> Resume | None:
    """Get resume for specific vacancy"""
    return db.query(Resume).filter(Resume.vacancy_id == vacancy_id).first()


def get_resumes_by_email(db: Session, email: str) -> list[Resume]:
    """Get all resumes by email address"""
    return db.query(Resume).filter(Resume.email == email).all()


def update_resume_path(db: Session, resume_id: int, path: str) -> Resume | None:
    """Update resume file path"""
    resume = get_resume_by_id(db, resume_id)
    if resume:
        resume.path = path
        db.commit()
        db.refresh(resume)
    return resume


def search_resumes_by_name(db: Session, name: str) -> list[Resume]:
    """Search resumes by full name"""
    return db.query(Resume).filter(Resume.fullname.contains(name)).all()


def get_all_resumes(db: Session, skip: int = 0, limit: int = 100) -> list[Resume]:
    """Get all resumes"""
    return db.query(Resume).offset(skip).limit(limit).all()


def delete_resume(db: Session, resume_id: int) -> bool:
    """Delete resume"""
    resume = get_resume_by_id(db, resume_id)
    if resume:
        db.delete(resume)
        db.commit()
        return True
    return False
