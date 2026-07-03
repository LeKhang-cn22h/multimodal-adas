import requests
import numpy as np
import cv2

CAMERA_URL = "http://camera-service:8005/frame"

def get_frame():

    response = requests.get(CAMERA_URL, timeout=1)

    response.raise_for_status()

    jpg = np.frombuffer(response.content, dtype=np.uint8)

    frame = cv2.imdecode(jpg, cv2.IMREAD_COLOR)

    return frame