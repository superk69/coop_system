# Dockerfile
FROM python:3.10-slim

# ติดตั้ง System Dependencies ที่จำเป็น (เช่น ตัวเชื่อมต่อ Postgres)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements และ install ก่อนเพื่อใช้ Cache ของ Docker
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy โค้ดทั้งหมดเข้า Container
COPY ./app /app/

# คำสั่งรัน Server (จะถูก Override ใน docker-compose ได้)
CMD ["gunicorn", "myproject.wsgi:application", "--bind", "0.0.0.0:8000"]