FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies. Versions are kept in sync with pyproject.toml.
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "sqlalchemy>=2.0" \
    "psycopg[binary]>=3.2" \
    "alembic>=1.13" \
    "pydantic>=2.9" \
    "pydantic-settings>=2.6"

EXPOSE 8000
