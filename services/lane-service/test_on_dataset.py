import os
import sys
import time
import cv2
import numpy as np
from tqdm import tqdm

sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.join(os.path.dirname(__file__), "app", "protos"))

from pipeline import LanePipeline
import adas_pb2

def main():
    # Duong dan dataset
    base_data_path = r"d:\NguyenNgocAnh\multimodal-adas\services\lane-service\data\solesensei-bdd100k"
    img_dir = os.path.join(base_data_path, "bdd100k", "bdd100k", "images", "10k", "val")
    output_dir = r"d:\NguyenNgocAnh\multimodal-adas\services\lane-service\data\bdd100k_test_results"
    
    os.makedirs(output_dir, exist_ok=True)
    
    if not os.path.exists(img_dir):
        print(f"Error: Directory {img_dir} does not exist!")
        return
        
    print("Khoi tao LanePipeline...")
    pipeline = LanePipeline()
    pipeline.update_config({
        "lane_detection": True,
        "deeplab_segmentation": False, # Chay OpenCV HSV+Canny vi chua train model pth
        "vehicle_detection": True
    })
    
    # Lay 20 anh dau tien tu validation set de test khach quan
    all_images = [f for f in os.listdir(img_dir) if f.endswith(".jpg")]
    test_images = all_images[:20]
    
    print(f"Bat dau chay suy luan (Inference) dong bo tren 20 anh tu dataset BDD100K...")
    
    for img_name in tqdm(test_images):
        img_path = os.path.join(img_dir, img_name)
        frame = cv2.imread(img_path)
        if frame is None:
            continue
            
        # Nén ảnh gui gRPC dong bo
        success, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if success:
            jpeg_bytes = buffer.tobytes()
            request = adas_pb2.FrameRequest(
                frame_id=999, # Frame ID gia lap
                timestamp=time.time(),
                image_bytes=jpeg_bytes
            )
            try:
                # Goi gRPC dong bo truc tiep (timeout 2s cho chac chan)
                response = pipeline.vehicle_client.AnalyzeFrame(request, timeout=2.0)
                
                # Cap nhat cache thu cong de pipeline su dung ve chuong ngai vat
                grpc_objects = []
                for obj in response.objects:
                    grpc_objects.append({
                        "track_id": obj.track_id,
                        "class_name": obj.class_name,
                        "distance": round(obj.distance, 1),
                        "color": obj.color,
                        "bbox": list(obj.bbox)
                    })
                
                pipeline.last_grpc_objects = grpc_objects
                pipeline.last_risk_level = response.risk_level
                pipeline.last_alert_msg = response.alert_msg
                pipeline.last_camera_occluded = response.camera_occluded
            except Exception as e:
                print(f"\nLoi goi gRPC dong bo cho anh {img_name}: {e}")
                pipeline.last_grpc_objects = []
        
        # Ep buoc pipeline khong tu kich hoat Thread bat dong bo (dat frame_counter khong chia het cho 3)
        pipeline.frame_counter = 1 
        
        # Chay ve ket qua (Overlay & Bounding boxes)
        pipeline.process_frame(frame, visualize=True)
        
        # Luu anh sau khi nhan dien xong
        out_path = os.path.join(output_dir, img_name)
        cv2.imwrite(out_path, frame)
        
    print(f"\n========================================================")
    print(f"Da hoan thanh chay suy luan (Inference)!")
    print(f"Toan bo 20 anh ket qua da duoc luu tai: {output_dir}")
    print(f"========================================================")

if __name__ == "__main__":
    main()
