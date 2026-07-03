FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgles2 \
    libegl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
    -o face_landmarker.task

COPY app/ app/

ENV PYTHONUNBUFFERED=1
ENV EAR_THRESHOLD=0.22
ENV DROWSY_FRAMES=60
ENV SLIDING_WINDOW_SIZE=90
ENV MODEL_PATH=face_landmarker.task
ENV PORT=8001
ENV LOG_LEVEL=INFO

EXPOSE 8001
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]