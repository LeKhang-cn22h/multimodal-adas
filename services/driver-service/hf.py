# import kagglehub
# import os

# path = kagglehub.dataset_download("samymesbah/nthu-dataset-ddd-multi-class")
# print("Path:", path)

# # Xem cấu trúc thư mục 2 cấp
# for root, dirs, files in os.walk(path):
#     level = root.replace(path, "").count(os.sep)
#     if level < 2:
#         print("  " * level + os.path.basename(root) + "/")
#         for f in files[:3]:
#             print("  " * (level + 1) + f)
#         if len(files) > 3:
#             print("  " * (level + 1) + f"... ({len(files)} files total)")

# # Download latest version
# path = kagglehub.dataset_download("tauilabdelilah/mrl-eye-dataset")

# print("Path to dataset files:", path)

# path = kagglehub.dataset_download("davidvazquezcic/yawn-dataset")

# print("Path to dataset files:", path)
# load libraries
from huggingface_hub import hf_hub_download
from ultralytics import YOLO
from supervision import Detections
from PIL import Image

# download model
model_path = hf_hub_download(repo_id="arnabdhar/YOLOv8-Face-Detection", filename="model.pt")


