FROM python:3.12-slim

WORKDIR /app

# Keep image small and predictable.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir --upgrade pip

# Install runtime deps (avoid relying on packaging metadata in this repo).
RUN pip install --no-cache-dir "fastapi>=0.115.0" "uvicorn>=0.30.0" "pydantic>=2.12.0"

COPY app ./app
COPY src ./src
COPY docs ./docs
COPY artifacts ./artifacts
COPY orchestration ./orchestration
COPY tools ./tools

EXPOSE 8080

# Cloud Run-style PORT env is common; default to 8080.
CMD ["sh", "-c", "python3 -m uvicorn app.server:app --host 0.0.0.0 --port ${PORT:-8080}"]

