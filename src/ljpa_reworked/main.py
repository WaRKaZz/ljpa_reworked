#!/usr/bin/env python

from ljpa_reworked.crew_workflow import (
    crewai_evaluate_vacancy,
    crewai_generate_email,
    crewai_generate_resume,
)
from ljpa_reworked.database import SessionLocal
from ljpa_reworked.operations import (
    create_email,
    create_evaluation,
    get_eligble_vacancies,
    update_vacancy,
)
from ljpa_reworked.workflow import (  # noqa
    extract_email,
    get_linkedin_posts,
    process_linkedin_posts,
    save_resume,
    save_vacancies,
    send_email,
    send_telegram_post,
    verified_recepient,
)


def main():
    with SessionLocal() as db:
        posts = get_linkedin_posts(db)
        vacancies = process_linkedin_posts(posts=posts, db=db)
        save_vacancies(vacancies, db)
        vacancies = get_eligble_vacancies(db=db)
        for vacancy in vacancies:
            recipient_email = extract_email(vacancy.credentials)

            evaluation = crewai_evaluate_vacancy(vacancy=vacancy)
            create_evaluation(
                db=db,
                vacancy_id=vacancy.id,
                evaluation_data=evaluation,
            )
            update_vacancy(db=db, vacancy_id=vacancy.id, processed=True)
            if not evaluation.rating > 50:
                continue

            resume = crewai_generate_resume(vacancy=vacancy, evaluation=evaluation)
            orm_resume = save_resume(resume, vacancy, db)

            if not recipient_email:
                send_telegram_post(vacancy=vacancy, db=db)
                continue
            elif not verified_recepient(recipient_email, db):
                continue

            email = crewai_generate_email(vacancy=vacancy)
            orm_email = create_email(
                db=db,
                vacancy_id=vacancy.id,
                email_data=email,
                recipient=recipient_email,
                resume_path=orm_resume.path,
            )
            send_email(orm_email, db)


if __name__ == "__main__":
    main()
