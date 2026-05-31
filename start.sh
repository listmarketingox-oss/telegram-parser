#!/bin/bash
set -e

export PYTHONPATH="${PYTHONPATH:-/app}"

echo "Running database migrations..."
python -m alembic upgrade head || echo "Migration warning (may be ok on first run)"

echo "Ensuring admin user exists..."
python -c "
import asyncio
from app.database import async_session
from app.models.user import AppUser
from app.services.auth import hash_password
from sqlalchemy import select

async def seed():
    async with async_session() as db:
        existing = await db.execute(select(AppUser).where(AppUser.email == 'admin@parser.local'))
        if not existing.scalar_one_or_none():
            user = AppUser(email='admin@parser.local', password_hash=hash_password('admin123'))
            db.add(user)
            await db.commit()
            print('Admin user created: admin@parser.local / admin123')
        else:
            print('Admin user already exists')

asyncio.run(seed())
" || echo "Seed warning"

echo "Starting web server on port ${PORT:-8000}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
