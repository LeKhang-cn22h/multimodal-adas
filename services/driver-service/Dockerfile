FROM python:3.11-slim

# Cài system deps cho OpenCV + MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy model file và code
COPY face_landmarker.task .
COPY main.py .

# ENV defaults — override bằng docker-compose hoặc .env
ENV EAR_THRESHOLD=0.22
ENV DROWSY_FRAMES=60
ENV CAMERA_ID=0
ENV AGGREGATOR_URL=http://aggregator-service:8003/event

CMD ["python", "main.py"]
