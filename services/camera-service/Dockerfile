FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8005
ENV CAMERA_INDEX=0
ENV JPEG_QUALITY=85
ENV FRAME_WIDTH=640
ENV FRAME_HEIGHT=480
ENV DEFAULT_FPS=30
ENV LOG_LEVEL=INFO
ENV SEATBELT_FRAME_INTERVAL=600
EXPOSE 8005
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
