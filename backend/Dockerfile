# ../backend/Dockerfile

# --- Stage 1: Build ---
# Use an official Python runtime as a parent image
FROM python:3.13-slim-bookworm AS builder

# Set environment variables
# PYTHONDONTWRITEBYTECODE: Prevents Python from writing .pyc files to disc (equivalent to python -B)
# PYTHONUNBUFFERED: Prevents Python from buffering stdin/stdout/stderr (useful for logging in containers)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for building Python packages (e.g., psycopg2, Pillow)
# libpq-dev is for psycopg2 (PostgreSQL adapter)
# build-essential, libjpeg-dev, zlib1g-dev are common for Pillow
# Add others if your requirements.txt needs them
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    # Add any other system dependencies your project might need for building wheels
    # For example, if you use libraries that compile C code: gcc, etc.
    && rm -rf /var/lib/apt/lists/*

# Install pipenv or poetry if you use them, or just copy requirements.txt
# Assuming requirements.txt
COPY requirements.txt .
# Upgrade pip and install dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# --- Stage 2: Final Application Image ---
FROM python:3.13-slim-bookworm

# Set environment variables (can be overridden by docker-compose)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE=foodgram.settings # Make sure this matches your project structure
# Set a non-root user (good security practice)
ENV APP_USER=django_user
RUN groupadd -r ${APP_USER} && useradd --no-log-init -r -g ${APP_USER} ${APP_USER}

# Set the working directory
WORKDIR /app

# Install only runtime system dependencies for psycopg2 and Pillow
# These were also in the builder stage, but ensure they are in the final image
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    # Add other runtime dependencies if needed
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from the builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/

# Copy the Django application code into the container
COPY . .

# Create directories for static and media files if they don't exist
# These will be mounted as volumes by docker-compose, but the directories should exist
RUN mkdir -p /app/staticfiles && \
    mkdir -p /app/media && \
    chown -R ${APP_USER}:${APP_USER} /app/staticfiles && \
    chown -R ${APP_USER}:${APP_USER} /app/media && \
    chown -R ${APP_USER}:${APP_USER} /app # Own the whole app directory

# Switch to the non-root user
USER ${APP_USER}
RUN python manage.py collectstatic --noinput --clear
# Expose the port Gunicorn will run on (matches docker-compose 'expose' and nginx 'proxy_pass')
# This is for documentation; docker-compose 'expose' actually handles inter-container communication.
EXPOSE 8000

# Command to run the application using Gunicorn
# The number of workers is often set to (2 * number_of_cores) + 1
# You can adjust --workers or make it configurable via an environment variable
# Ensure 'foodgram.wsgi:application' matches your project's WSGI application path
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "foodgram.wsgi:application"]