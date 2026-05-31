#!/bin/bash

export PYTHONPATH="${PYTHONPATH:-/app}"

echo "=== TG Parser startup ==="
echo "Python: $(python --version)"
echo "Port: ${PORT:-8000}"

echo "Running database migrations..."
python -m alembic upgrade head
if [ $? -ne 0 ]; then
    echo "WARNING: Migrations failed, continuing..."
fi

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
" || echo "WARNING: Seed failed"

echo "Starting web server on port ${PORT:-8000}..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info
