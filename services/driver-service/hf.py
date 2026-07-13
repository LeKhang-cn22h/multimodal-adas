import kagglehub
import os

path = kagglehub.dataset_download("samymesbah/nthu-dataset-ddd-multi-class")
print("Path:", path)

# Xem cấu trúc thư mục 2 cấp
for root, dirs, files in os.walk(path):
    level = root.replace(path, "").count(os.sep)
    if level < 2:
        print("  " * level + os.path.basename(root) + "/")
        for f in files[:3]:
            print("  " * (level + 1) + f)
        if len(files) > 3:
            print("  " * (level + 1) + f"... ({len(files)} files total)")