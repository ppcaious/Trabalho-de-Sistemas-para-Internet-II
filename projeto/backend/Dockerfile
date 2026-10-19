FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências primeiro, para aproveitar o cache de camadas do Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY . .

# Usuário sem privilégios
RUN useradd --create-home --shell /bin/bash api && chown -R api:api /app
USER api

EXPOSE 8000

# Gunicorn (WSGI) com múltiplos workers e threads - ver gunicorn.conf.py
CMD ["gunicorn", "--config", "gunicorn.conf.py", "wsgi:app"]
