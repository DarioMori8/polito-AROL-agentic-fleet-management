# Built with the repo root as context (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# Shared schemas, installed by requirements.txt as -e ../shared/contracts
COPY shared/contracts /shared/contracts

# Dependencies first, so code changes don't invalidate the pip layer
COPY agents/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/ .

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
