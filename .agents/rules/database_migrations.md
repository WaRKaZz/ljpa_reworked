---
trigger: always_on
---

# Database Migrations Rule

**CRITICAL REQUIREMENT:**
Any time a modification is made to an SQLAlchemy model in `src/ljpa_reworked/models/` (e.g., adding a column, changing a type, or adding a new table), you **MUST** generate an Alembic migration.

**Procedure:**
1. Make your changes to the Python models.
2. Run `alembic revision --autogenerate -m "description of your change"`.
3. Verify the generated migration file in `src/ljpa_reworked/migrations/versions/`.
4. Apply it using `alembic upgrade head`.

Failing to generate and apply migrations will result in database inconsistency and application crashes.
