FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
    -o face_landmarker.task

COPY app/ .

ENV EAR_THRESHOLD=0.22
ENV DROWSY_FRAMES=60
ENV CAMERA_ID=0
ENV AGGREGATOR_URL=http://aggregator-service:8003/event
ENV PORT=8001

EXPOSE 8001
CMD ["python", "main.py"]
