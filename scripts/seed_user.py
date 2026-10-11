#!/usr/bin/env python3
"""
Seed a default demo user so you can sign in without registering.

    email:    user@test.com
    password: user

Run from the repo root (or backend/) with the backend venv active and the
database already migrated:

    source backend/.venv/bin/activate
    python scripts/seed_user.py

The script is idempotent — running it again will not create a duplicate.
"""

import asyncio
import os
import sys
import uuid

# Make the backend package importable regardless of where this is run from.
BACKEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"
)
sys.path.insert(0, BACKEND_DIR)

from app.database import async_session  # noqa: E402
from app.repos import user_repo  # noqa: E402
from app.utils.auth import hash_password  # noqa: E402

# The login form validates this field as an email, so it must be a valid
# address even though the password is just "user".
DEMO_EMAIL = "user@test.com"
DEMO_PASSWORD = "user"


async def seed() -> None:
    async with async_session() as db:
        existing = await user_repo.get_by_email(db, DEMO_EMAIL)
        if existing:
            print(
                f"Demo user '{DEMO_EMAIL}' already exists (id={existing.id}); nothing to do."
            )
            return

        user = await user_repo.create(
            db,
            email=DEMO_EMAIL,
            hashed_password=hash_password(DEMO_PASSWORD),
            first_name="Demo",
            last_name="User",
            country="NZ",
            currency="NZD",
            email_verified=True,
            created_by=uuid.uuid4(),  # placeholder; repointed to self below
        )
        # created_by is non-nullable (AuditMixin); point it at the user itself.
        user.created_by = user.id
        await db.commit()
        print(
            f"Created demo user (id={user.id}). Sign in with {DEMO_EMAIL} / {DEMO_PASSWORD}."
        )


if __name__ == "__main__":
    asyncio.run(seed())
