# ../backend/Dockerfile

# --- Stage 1: Build ---
    FROM python:3.13-slim-bookworm AS builder

    ENV PYTHONDONTWRITEBYTECODE 1
    ENV PYTHONUNBUFFERED 1
    WORKDIR /app
    
    # Install build-time system dependencies
    RUN apt-get update && \
        apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg-dev \
        zlib1g-dev \
        && rm -rf /var/lib/apt/lists/*
    
    COPY requirements.txt .
    RUN pip install --upgrade pip && \
        pip install --no-cache-dir -r requirements.txt
    
    # --- Stage 2: Final Application Image ---
    FROM python:3.13-slim-bookworm
    
    ENV PYTHONDONTWRITEBYTECODE 1
    ENV PYTHONUNBUFFERED 1
    ENV DJANGO_SETTINGS_MODULE=foodgram.settings
    ENV APP_USER=django_user
    
    RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} ${APP_USER}
    
    WORKDIR /app
    
    # Install runtime system dependencies
    RUN apt-get update && \
        apt-get install -y --no-install-recommends \
        libpq5 \
        libjpeg62-turbo \
        && rm -rf /var/lib/apt/lists/*
    
    # Copy installed Python packages from the builder stage
    COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
    COPY --from=builder /usr/local/bin/ /usr/local/bin/
    
    # Copy the Django application code
    COPY . .
    
    # Create staticfiles and media directories and set ownership
    # staticfiles is where collectstatic will put files
    # media is for user uploads
    RUN mkdir -p /app/staticfiles && \
        mkdir -p /app/media && \
        chown -R ${APP_USER}:${APP_USER} /app/staticfiles && \
        chown -R ${APP_USER}:${APP_USER} /app/media && \
        chown -R ${APP_USER}:${APP_USER} /app
    
    USER ${APP_USER}
    
    # Collect static files (this will be run by the entrypoint later, but good to have if testing image standalone)
    # RUN python manage.py collectstatic --noinput --clear
    
    EXPOSE 8000
    
    # CMD is removed here because it will be handled by docker-compose and entrypoint.sh
    # CMD ["gunicorn", "--bind", "0.0.0.0:8000", "foodgram.wsgi:application"]