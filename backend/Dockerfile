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
    "pydantic-settings>=2.6" \
    "httpx>=0.27"

# Dev-time tooling (pytest for the test suite, ruff for linting).
# Mirrors pyproject.toml's [project.optional-dependencies] dev.
RUN pip install --no-cache-dir \
    "pytest>=8.0" \
    "ruff>=0.7"

EXPOSE 8000
