FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8007
ENV CAMERA_SERVICE_URL=http://camera-service:8005
ENV MODEL_PATH=best.pt
ENV CONFIDENCE_THRESHOLD=0.3
ENV WARNING_FRAMES=10
ENV POLL_INTERVAL=3.0
ENV LOG_LEVEL=INFO
EXPOSE 8007
CMD ["python", "main.py"]
