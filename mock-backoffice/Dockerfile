# Built with the repo root as context (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# Dependencies first, so code changes don't invalidate the pip layer
COPY mock-backoffice/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mock-backoffice/ .

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--reload"]
