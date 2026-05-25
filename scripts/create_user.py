"""Create an admin user from the command line.

Usage: python -m scripts.create_user admin@example.com mypassword
"""
import asyncio
import sys

from sqlalchemy import select

from app.database import async_session
from app.models.user import AppUser
from app.services.auth import hash_password


async def main():
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.create_user <email> <password>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    async with async_session() as db:
        existing = await db.execute(select(AppUser).where(AppUser.email == email))
        if existing.scalar_one_or_none():
            print(f"User {email} already exists")
            sys.exit(1)

        user = AppUser(email=email, password_hash=hash_password(password))
        db.add(user)
        await db.commit()
        print(f"User {email} created successfully")


if __name__ == "__main__":
    asyncio.run(main())
