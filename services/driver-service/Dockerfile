FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgles2 \
    libegl1 \
    libx11-6 \
    libgtk-3-0 \
    python3-tk \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p app/models \
    && curl -L "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task" \
    -o app/models/face_landmarker.task

COPY app/ .

ENV EAR_THRESHOLD=0.22
ENV DROWSY_FRAMES=60
ENV SLIDING_WINDOW_SIZE=90
ENV MODEL_PATH=app/models/face_landmarker.task
ENV PORT=8001

EXPOSE 8001
CMD ["python", "main.py"]
