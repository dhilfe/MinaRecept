#!/bin/sh

# Om vi kör mot Postgres, vänta tills DB är uppe
if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Kör migreringar
echo "Applying database migrations..."
python manage.py migrate

# Samla statiska filer
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Starta servern med Gunicorn
echo "Starting Gunicorn..."
exec gunicorn receptapp_project.wsgi:application --bind 0.0.0.0:8000 --workers 3

