FROM python:3.11-slim AS builder


COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv pip install --system --no-cache -r pyproject.toml

FROM python:3.11-slim

WORKDIR /app

# Запрещаем Python создавать .pyc файлы и включаем моментальный вывод логов
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Важно: добавляем src в пути поиска Python, чтобы работали импорты 'from ljpa_reworked'
ENV PYTHONPATH=/app/src

# Копируем установленные библиотеки из билдера
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Теперь копируем сам код приложения
COPY . .

# Устанавливаем сам проект как пакет (теперь ljpa_reworked виден системе)
# Мы используем 'uv' из первого этапа, если он нужен, но тут достаточно просто python
RUN pip install --no-deps .

# Запуск: сначала миграции, потом приложение через модуль (-m)
CMD ["/bin/bash", "-c", "alembic upgrade head && python -m ljpa_reworked.main"]