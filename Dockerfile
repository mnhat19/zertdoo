# === Zertdoo Dockerfile ===
# Dung cho deploy len Render (hoac bat ky platform nao ho tro Docker)

FROM python:3.11-slim

# Khong tao .pyc, in log ngay lap tuc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cai dependencies truoc (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toan bo code
COPY . .

# Render su dung PORT env var (thuong la 10000), mac dinh 8000 cho local
EXPOSE 8000

# QUAN TRONG: Render truyen PORT env var dong, phai dung shell form de doc $PORT
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
