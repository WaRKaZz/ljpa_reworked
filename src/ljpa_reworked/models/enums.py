from enum import Enum


class VacancyStatus(str, Enum):
    created = "created"  # discovered/upserted; not yet reviewed
    updated = "updated"  # source fields refreshed on existing vacancy
    reviewed = "reviewed"  # review completed and candidate may proceed
    rejected = "rejected"  # review completed; not a match
    review_error = "review_error"  # review could not complete; may be retried
    application_prepared = "application_prepared"  # materials ready, not submitted
    applied = "applied"  # submission confirmed
    application_error = "application_error"  # application attempt failed; may retry
    withdrawn = "withdrawn"  # candidate withdrew; never auto-submit
    expired = "expired"  # source says vacancy is no longer active
    archived = "archived"  # deliberately excluded from active workflow
