FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DO_DATA_DIR=/app/data \
    DO_REPORTS_DIR=/app/reports \
    DO_ARCHIVE_DIR=/app/archive

WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY digital_oracle ./digital_oracle
COPY web ./web
COPY SKILL.md README.md LICENSE ./
RUN mkdir -p /app/data /app/reports /app/archive \
    && chown -R app:app /app

USER app
EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "--timeout", "180", "web.wsgi:app"]
