"""This package contains database operations for various models."""

from .email_ops import (
    create_email,
    delete_email,
    get_email_by_id,
    get_emails_by_recipient,
    get_emails_by_vacancy,
    get_pending_emails,
    get_sent_emails,
    mark_email_sent,
    search_emails_by_subject,
    update_email,
)
from .evaluation_ops import (
    create_evaluation,
    delete_evaluation,
    get_evaluation_by_id,
    get_evaluation_by_vacancy,
    get_evaluations_by_rating_range,
    get_top_rated_vacancies,
    get_unrated_vacancies,
    update_evaluation,
)
from .linkedin_post_ops import (
    create_linkedin_post,
    get_all_linkedin_posts,
    get_duplicate_post,
    get_linkedin_post_by_id,
    get_linkedin_posts_by_vacancy,
    get_unprocessed_linkedin_posts,
    link_post_to_vacancy,
    mark_linkedin_post_as_processed,
    search_linkedin_posts_by_text,
    soft_delete_linkedin_post,
    update_linkedin_post,
)
from .resume_ops import (
    create_resume,
    delete_resume,
    get_all_resumes,
    get_resume_by_id,
    get_resume_by_vacancy,
    get_resumes_by_email,
    search_resumes_by_name,
    update_resume_path,
)
from .telegram_ops import mark_vacancy_as_sent
from .vacancy_ops import (
    create_vacancy,
    get_all_vacancies,
    get_eligble_vacancies,
    get_vacancies_by_source,
    get_vacancies_by_visa_status,
    get_vacancy_by_id,
    search_vacancies,
    soft_delete_vacancy,
    update_vacancy,
)

__all__ = [
    # email_ops
    "create_email",
    "mark_vacancy_as_sentcreate_email",
    "delete_email",
    "get_email_by_id",
    "get_emails_by_recipient",
    "get_emails_by_vacancy",
    "get_pending_emails",
    "get_sent_emails",
    "mark_email_sent",
    "search_emails_by_subject",
    "update_email",
    # evaluation_ops
    "create_evaluation",
    "delete_evaluation",
    "get_evaluation_by_id",
    "get_evaluation_by_vacancy",
    "get_eligble_vacancies",
    "get_evaluations_by_rating_range",
    "get_top_rated_vacancies",
    "get_unrated_vacancies",
    "update_evaluation",
    # linkedin_post_ops
    "create_linkedin_post",
    "get_all_linkedin_posts",
    "get_linkedin_post_by_id",
    "get_linkedin_posts_by_vacancy",
    "get_unprocessed_linkedin_posts",
    "mark_linkedin_post_as_processed",
    "search_linkedin_posts_by_text",
    "soft_delete_linkedin_post",
    "update_linkedin_post",
    "link_post_to_vacancy",
    "get_duplicate_post"
    # resume_ops
    "create_resume",
    "delete_resume",
    "get_all_resumes",
    "get_resume_by_id",
    "get_resume_by_vacancy",
    "get_resumes_by_email",
    "search_resumes_by_name",
    "update_resume_path",
    # vacancy_ops
    "create_vacancy",
    "get_all_vacancies",
    "get_vacancies_by_source",
    "get_vacancies_by_visa_status",
    "get_vacancy_by_id",
    "search_vacancies",
    "soft_delete_vacancy",
    "update_vacancy",
    # telegram_ops
    "mark_vacancy_as_sent",
]
