FROM python:3.12-slim

# чтобы логи сразу шли в stdout
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# системные зависимости (на всякий под asyncpg)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# копируем зависимости
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# копируем код
COPY . .

# порт FastAPI
EXPOSE 8000

# запуск
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]