FROM python:3.12-slim
WORKDIR /app

# Install timezone data for proper timezone support
RUN apt-get update && apt-get install -y tzdata && rm -rf /var/lib/apt/lists/*

# Set timezone to CET (GMT+1)
ENV TZ=CET

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY permissions.yml .
COPY app app
COPY permissions.yml .
COPY start_consumer.py .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
