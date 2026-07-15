from pathlib import Path

APP_DIR = Path(__file__).resolve().parent

MODEL_DIR = APP_DIR / "models"

EYE_MODEL = MODEL_DIR / "eye_state_model.pt"

MOUTH_MODEL = MODEL_DIR / "mouth_state_model.pt"

FACE_LANDMARKER = MODEL_DIR / "face_landmarker.task"
SEATBELT_MODEL = MODEL_DIR / "best.pt"
