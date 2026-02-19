FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Системные зависимости для asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости (кэшируются отдельным слоем)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY src/ ./src/
COPY data/fonts/ ./data/fonts/
COPY data/varieties_reference.json ./data/varieties_reference.json

# Директории для runtime данных (монтируются как volumes)
RUN mkdir -p data/avatars data/guides data/documents data/prompt_documents

EXPOSE 8080

CMD ["python", "-m", "src"]
