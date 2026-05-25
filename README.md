# Telegram Parser

Internal service for collecting messages from Telegram channels/groups by keywords with time filtering.

## Stack

- Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic
- Telethon (MTProto) for Telegram access
- PostgreSQL 16
- Jinja2 server-side rendering
- Railway deployment (web + worker)

## Quick Start

```bash
# Start PostgreSQL
docker-compose up -d

# Create venv & install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — set ENCRYPTION_KEY (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Run migrations
alembic upgrade head

# Create first user
python -m scripts.create_user admin@example.com yourpassword

# Start web
uvicorn app.main:app --reload --port 8000

# Start worker (separate terminal)
python -m app.worker
```

## Tests

```bash
pytest tests/ -v
```
