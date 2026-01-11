FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements-prod.txt /app/requirements-prod.txt
RUN pip install -r /app/requirements-prod.txt

COPY . /app

ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
