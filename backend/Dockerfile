# ── DeadZero v3.0 — Dockerfile ───────────────────────────────────────────────
# Used for Render.com deployment.
# Build : docker build -t deadzero-backend .
# Run   : docker run -p 8000:8000 --env-file .env deadzero-backend

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for matplotlib / scipy
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create exports directory
RUN mkdir -p /app/exports

# Expose port
EXPOSE 8000

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
