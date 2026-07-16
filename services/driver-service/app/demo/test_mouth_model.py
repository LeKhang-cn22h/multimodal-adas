from PIL import Image
from app.services.classifiers.mouth_classifier import MouthClassifier
from app.config import MOUTH_MODEL

classifier = MouthClassifier(MOUTH_MODEL)

# THAY đường dẫn này bằng vài ảnh thật trong dataset của bạn
# (folder no_yawn và yawn dùng để train/val)
test_images = [
    r"D:\multimodal-adas\services\driver-service\dataset\yawn-dataset\no yawn\2761.jpg",
    r"D:\multimodal-adas\services\driver-service\dataset\yawn-dataset\no yawn\2762.jpg",
    r"D:\multimodal-adas\services\driver-service\dataset\yawn-dataset\yawn\1.jpg",
    r"D:\multimodal-adas\services\driver-service\dataset\yawn-dataset\yawn\2.jpg",
]

for img_path in test_images:
    img = Image.open(img_path).convert("RGB")
    result = classifier.predict(img)
    print(f"{img_path} -> {result}")