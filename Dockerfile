# ============================================================================
# ProductGuard Production Multi-Stage Dockerfile
# Python 3.11 with TensorFlow-CPU, OpenCV, and Keras
# ============================================================================

FROM python:3.11-slim

# Prevent Python from writing pyc files to disc & buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    KERAS_HOME=/app/.keras \
    TF_ENABLE_ONEDNN_OPTS=0 \
    FLASK_CONFIG=production

WORKDIR /app

# Install system dependencies required by OpenCV and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary upload, cache, and model directories
RUN mkdir -p /app/app/static/uploads/references \
             /app/app/static/uploads/scans \
             /app/app/static/uploads/embeddings \
             /app/.keras/models

# Copy project source code
COPY . /app

# Pre-download or verify permissions for non-root security
RUN chmod -R 777 /app/app/static/uploads /app/.keras

# Healthcheck to verify the web service is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

EXPOSE 5000

# Start production server using Gunicorn WSGI
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
