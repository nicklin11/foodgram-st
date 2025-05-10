#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Waiting for PostgreSQL to be ready..."
# Use netcat (nc) if available, or a simple loop.
# This is a basic check; for robust production, use pg_isready if pg_client is installed
# or a more sophisticated wait-for-it script.
# Since we have healthcheck in docker-compose, this might be redundant but good for clarity.
# For alpine, netcat is often `nc`. For debian/ubuntu based, it's `netcat`.
# Let's assume a simple loop as nc might not be in python:slim.
# The depends_on with service_healthy condition in docker-compose is better.

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files (already in Dockerfile, but can be here too)
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

# Load initial data (if needed and not already handled by migrations)
# Check if ingredients need loading (e.g., by counting them)
INGREDIENT_COUNT=$(python manage.py shell -c "from api.models import Ingredient; print(Ingredient.objects.count())")
if [ "$INGREDIENT_COUNT" -eq 0 ]; then
  echo "Loading ingredients..."
  python manage.py load_ingredients
else
  echo "Ingredients already loaded."
fi


# Create superuser if DJANGO_SUPERUSER_USERNAME is set and user doesn't exist
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Checking for superuser..."
  python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='${DJANGO_SUPERUSER_USERNAME}').exists():
    User.objects.create_superuser('${DJANGO_SUPERUSER_USERNAME}', '${DJANGO_SUPERUSER_EMAIL}', '${DJANGO_SUPERUSER_PASSWORD}')
    print('Superuser ${DJANGO_SUPERUSER_USERNAME} created.')
else:
    print('Superuser ${DJANGO_SUPERUSER_USERNAME} already exists.')
"
else
    echo "Superuser credentials not set in environment, skipping automatic creation."
fi

# Start Gunicorn server (this will be the CMD from docker-compose)
echo "Starting Gunicorn..."
exec "$@"