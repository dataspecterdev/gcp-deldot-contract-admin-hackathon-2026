FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY api ./api
COPY config ./config
COPY prompts ./prompts
COPY References ./References
COPY Evaluation ./Evaluation

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1
ENV GOOGLE_CLOUD_PROJECT=hackathon-2026-transport-2
ENV GOOGLE_CLOUD_LOCATION=us-central1
ENV CCRF_USE_RAG=0
ENV PORT=8080

EXPOSE 8080

CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}
