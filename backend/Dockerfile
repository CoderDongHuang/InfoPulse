# ============================================================
# InfoPulse Backend Docker Image (Full Version — with Chromium)
# ============================================================
# Build:
#   docker build -t infopulse-backend -f Dockerfile .
# Run:
#   docker run --rm -p 8000:8000 --env-file .env infopulse-backend
# ============================================================

FROM python:3.11-slim-bookworm

# Prevent Python from buffering stdout/stderr (important for log visibility)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# --- Install system dependencies for Playwright + Chromium ---
# These are the native libraries Chromium needs at runtime.
# Without them, you get "error while loading shared libraries" on startup.
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Chromium core deps
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxext6 \
    libxfixes3 \
    libxrender1 \
    libxi6 \
    libxtst6 \
    # Utility
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Install Python dependencies ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Install Chromium browser ---
# playwright install-deps installs any remaining system libraries.
# This step downloads ~150MB Chromium binary.
RUN playwright install chromium
RUN playwright install-deps chromium

# --- Copy application code ---
COPY . .

# --- Expose port ---
EXPOSE 8000

# --- Start the app ---
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
