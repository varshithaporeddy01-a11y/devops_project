FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app
RUN addgroup --system graphmind && adduser --system --ingroup graphmind --home /app graphmind
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=graphmind:graphmind . .
RUN mkdir -p /app/data && chown -R graphmind:graphmind /app
USER graphmind

ENV DATABASE_PATH=/app/data/graphmind.db
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
