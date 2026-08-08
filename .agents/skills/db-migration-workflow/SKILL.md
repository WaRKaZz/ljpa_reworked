---
name: db-migration-workflow
description: Step-by-step scenario for generating and verifying SQLAlchemy/Alembic database migrations.
---

# Database Migration Workflow Skill

This skill guides the process of safely applying changes to the database schema.

## When to use

Use this skill whenever you are instructed to modify database models in `src/ljpa_reworked/models/`.

## Instructions

1. **Model Updates**: Make the necessary Python code changes in the SQLAlchemy model files.
2. **Generate Migration**: Run the following command in the terminal to autogenerate a migration script:
   ```bash
   alembic revision --autogenerate -m "Add descriptive message here"
   ```
3. **Verify Migration Script**: Open the newly generated file in `src/ljpa_reworked/migrations/versions/`. Ensure that the `upgrade()` and `downgrade()` functions correctly reflect your intended changes and do not accidentally drop unrelated tables.
4. **Apply Migration**: Run the upgrade command to apply the changes to the database:
   ```bash
   alembic upgrade head
   ```
5. **Testing**: Test the application to ensure the database interacts correctly with the updated schema.
