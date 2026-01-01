# Använd en lättviktig Python-bild (slim varianten är mindre och säkrare)
FROM python:3.11-slim

# Sätt arbetskatalog
WORKDIR /app

# Sätt miljövariabler för att förhindra .pyc-filer och buffring
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Installera systemberoenden (krävs för Postgres och byggverktyg)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installera Python-beroenden
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Installera Gunicorn för produktion
RUN pip install gunicorn

# Kopiera projektfilerna
COPY . .

# Gör entrypoint exekverbar
RUN chmod +x /app/entrypoint.sh

# Exponera port (dock internt i containern)
EXPOSE 8000

# Kör entrypoint-scriptet
ENTRYPOINT ["/app/entrypoint.sh"]

