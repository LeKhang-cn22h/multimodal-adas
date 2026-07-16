import os
import json
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
import torchvision.transforms as T

class BDD100KDataset(Dataset):
    def __init__(self, img_dir, json_path, img_size=(640, 360), is_train=True):
        self.img_dir = img_dir
        self.img_size = img_size
        self.is_train = is_train
        
        # Doc danh sach file anh thuc te co trong thu muc
        self.img_names = [f for f in os.listdir(img_dir) if f.endswith('.jpg')]
        self.img_set = set(self.img_names)
        
        print(f"Loading annotations from {json_path}...")
        with open(json_path, 'r') as f:
            all_annos = json.load(f)
            
        # Chi giu lai nhung annotation co file anh thuc te trong thu muc
        self.annos = {}
        for anno in all_annos:
            name = anno['name']
            if name in self.img_set:
                self.annos[name] = anno['labels']
                
        # Cap nhat lai danh sach anh thuc te co label hop le
        self.img_names = [name for name in self.img_names if name in self.annos]
        print(f"Found {len(self.img_names)} valid images with annotations.")
        
        # Image transforms
        self.transform = T.Compose([
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

    def __len__(self):
        return len(self.img_names)

    def __getitem__(self, idx):
        img_name = self.img_names[idx]
        img_path = os.path.join(self.img_dir, img_name)
        
        # Doc anh
        img = cv2.imread(img_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        
        # Tao mask trong (0: Background)
        mask = np.zeros((h, w), dtype=np.uint8)
        
        labels = self.annos[img_name]
        
        # 1. Ve Drivable Area (Lop 1)
        for label in labels:
            if label['category'] == 'drivable area':
                if 'poly2d' in label:
                    for poly in label['poly2d']:
                        pts = np.array(poly['vertices'], dtype=np.int32)
                        cv2.fillPoly(mask, [pts], 1)
                        
        # 2. Ve Lane Markings (Lop 2)
        for label in labels:
            if label['category'] == 'lane':
                if 'poly2d' in label:
                    for poly in label['poly2d']:
                        pts = np.array(poly['vertices'], dtype=np.int32)
                        # Ve duong voi do day = 8 pixel de AI de dang hoc
                        cv2.polylines(mask, [pts], isClosed=False, color=2, thickness=8)
                        
        # Resize anh va mask ve kich thuoc train
        img_resized = cv2.resize(img, self.img_size, interpolation=cv2.INTER_LINEAR)
        mask_resized = cv2.resize(mask, self.img_size, interpolation=cv2.INTER_NEAREST)
        
        # Data augmentation ngau nhien neu dang train
        if self.is_train and np.random.rand() > 0.5:
            # Lat ngang (Horizontal Flip)
            img_resized = cv2.flip(img_resized, 1)
            mask_resized = cv2.flip(mask_resized, 1)

        # Convert to tensor
        img_tensor = self.transform(img_resized)
        mask_tensor = torch.from_numpy(mask_resized).long()
        
        return img_tensor, mask_tensor
