FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
RUN --mount=type=cache,target=/root/.cache/pip python -c "import subprocess,tomllib; p=tomllib.load(open('pyproject.toml','rb'))['project']; subprocess.check_call(['python','-m','pip','install',*p['dependencies'],*p['optional-dependencies']['gemini']])"
COPY alembic ./alembic
COPY app ./app
COPY data ./data
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-deps "."

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
