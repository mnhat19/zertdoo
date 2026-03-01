# === Zertdoo Dockerfile ===
# Dung cho deploy len Koyeb (hoac bat ky platform nao ho tro Docker)

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

# Koyeb yeu cau expose port (mac dinh 8000)
EXPOSE 8000

# Chay FastAPI bang uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
