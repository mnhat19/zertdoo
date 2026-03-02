# === Zertdoo Dockerfile ===
# Dung cho deploy len Render (hoac bat ky platform nao ho tro Docker)

FROM python:3.11-slim

# Khong tao .pyc, in log ngay lap tuc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Giam memory footprint: Python tra memory ve OS som hon
ENV MALLOC_TRIM_THRESHOLD_=65536

WORKDIR /app

# Cai dependencies truoc (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Copy toan bo code
COPY . .

# Render su dung PORT env var (thuong la 10000), mac dinh 8000 cho local
EXPOSE 8000

# 1 worker (phu hop voi free tier 512MB), --no-access-log giam overhead log
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
