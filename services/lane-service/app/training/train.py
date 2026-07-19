import os
import argparse
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from dataset import BDD100KDataset
from model import get_model

def calculate_iou(pred, target, num_classes=3):
    """
    Tinh toan Mean IoU cho cac class.
    """
    ious = []
    # Lay class duoc du doan co xac suat cao nhat
    pred = torch.argmax(pred, dim=1)
    
    for cls in range(num_classes):
        pred_cls = (pred == cls)
        target_cls = (target == cls)
        
        intersection = (pred_cls & target_cls).float().sum()
        union = (pred_cls | target_cls).float().sum()
        
        if union == 0:
            ious.append(float('nan'))  # Khong co pixel nao thuoc class nay
        else:
            ious.append((intersection / union).item())
            
    return ious

def main():
    parser = argparse.ArgumentParser(description="Train DeepLabV3 for Lane and Road Segmentation")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=8, help="Batch size for training")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--num_workers", type=int, default=4, help="Number of dataloader workers")
    parser.add_argument("--save_dir", type=str, default="models", help="Directory to save the trained model")
    args = parser.parse_args()

    # Thiet lap thiet bi (uu tien CUDA neu co Card NVIDIA)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    if device.type == "cuda":
        print(f"GPU Model: {torch.cuda.get_device_name(0)}")

    os.makedirs(args.save_dir, exist_ok=True)

    # Khai bao duong dan file tuong doi/tuyet doi trong workspace
    # __file__ la lane-service/app/training/train.py -> di len 3 cap de den lane-service/
    lane_service_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base_data_path = os.path.join(lane_service_dir, "data", "solesensei-bdd100k")
    
    # Neu chay tren Colab hoac thu muc khac, cho phep lay tu thu muc data cua training neu co
    if not os.path.exists(base_data_path):
        base_data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "solesensei-bdd100k")
    
    train_img_dir = os.path.join(base_data_path, "bdd100k", "bdd100k", "images", "10k", "train")
    train_json = os.path.join(base_data_path, "bdd100k_labels_release", "bdd100k", "labels", "bdd100k_labels_images_train.json")
    
    val_img_dir = os.path.join(base_data_path, "bdd100k", "bdd100k", "images", "10k", "val")
    val_json = os.path.join(base_data_path, "bdd100k_labels_release", "bdd100k", "labels", "bdd100k_labels_images_val.json")

    # Khoi tao datasets
    print("Initializing Train Dataset...")
    train_dataset = BDD100KDataset(train_img_dir, train_json, img_size=(640, 360), is_train=True)
    print("Initializing Val Dataset...")
    val_dataset = BDD100KDataset(val_img_dir, val_json, img_size=(640, 360), is_train=False)

    # Khoi tao dataloaders
    train_loader = DataLoader(
        train_dataset, 
        batch_size=args.batch_size, 
        shuffle=True, 
        num_workers=args.num_workers,
        pin_memory=True if device.type == "cuda" else False,
        drop_last=True
    )
    val_loader = DataLoader(
        val_dataset, 
        batch_size=args.batch_size, 
        shuffle=False, 
        num_workers=args.num_workers,
        pin_memory=True if device.type == "cuda" else False
    )

    # Khoi tao mo hinh
    model = get_model(num_classes=3)
    model.to(device)

    # Class weights de giai quyet mat can bang du lieu (Lane rat nho so voi Nen/Duong)
    # 0: Background, 1: Drivable Area, 2: Lane Markings
    class_weights = torch.tensor([1.0, 2.0, 10.0]).to(device)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    # TensorBoard writer
    writer = SummaryWriter(log_dir="runs/deeplab_segmentation")

    best_val_iou = 0.0

    print("Starting training loop...")
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_loss = 0.0
        
        # ProgressBar
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch}/{args.epochs}")
        for images, masks in progress_bar:
            images = images.to(device)
            masks = masks.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            
            # DeepLabV3 tra ve dict co 'out' (chinh) va 'aux' (phu)
            loss = criterion(outputs['out'], masks)
            if 'aux' in outputs and outputs['aux'] is not None:
                loss_aux = criterion(outputs['aux'], masks)
                loss = loss + 0.4 * loss_aux
                
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item()
            progress_bar.set_postfix({"Loss": f"{loss.item():.4f}"})

        scheduler.step()
        avg_train_loss = epoch_loss / len(train_loader)
        writer.add_scalar("Loss/Train", avg_train_loss, epoch)

        # Validation phase
        model.eval()
        val_loss = 0.0
        val_ious = [0.0, 0.0, 0.0]
        valid_batches = 0
        
        with torch.no_grad():
            for images, masks in tqdm(val_loader, desc="Validating"):
                images = images.to(device)
                masks = masks.to(device)

                outputs = model(images)
                loss = criterion(outputs['out'], masks)
                val_loss += loss.item()

                # Tinh IoU cho tung batch
                batch_ious = calculate_iou(outputs['out'], masks)
                for i in range(3):
                    if not torch.isnan(torch.tensor(batch_ious[i])):
                        val_ious[i] += batch_ious[i]
                valid_batches += 1

        avg_val_loss = val_loss / len(val_loader)
        avg_val_ious = [val_ious[i] / valid_batches for i in range(3)]
        mean_val_iou = sum(avg_val_ious[1:]) / 2.0  # Tinh trung binh IoU cua Road va Lane (bo qua Background)

        print(f"\nEpoch {epoch} Results:")
        print(f"  Train Loss: {avg_train_loss:.4f}")
        print(f"  Val Loss: {avg_val_loss:.4f}")
        print(f"  Val IoU (Road): {avg_val_ious[1]*100:.2f}%")
        print(f"  Val IoU (Lane): {avg_val_ious[2]*100:.2f}%")
        print(f"  Mean Val IoU (Road+Lane): {mean_val_iou*100:.2f}%")

        # Ghi log TensorBoard
        writer.add_scalar("Loss/Val", avg_val_loss, epoch)
        writer.add_scalar("IoU/Road", avg_val_ious[1], epoch)
        writer.add_scalar("IoU/Lane", avg_val_ious[2], epoch)
        writer.add_scalar("IoU/Mean", mean_val_iou, epoch)

        # Luu trong so tot nhat dua tren Mean IoU cua Road va Lane
        if mean_val_iou > best_val_iou:
            best_val_iou = mean_val_iou
            best_model_path = os.path.join(args.save_dir, "best_deeplab.pth")
            torch.save(model.state_dict(), best_model_path)
            print(f"  --> Saved new best model to {best_model_path} with Mean IoU: {mean_val_iou*100:.2f}%")

    writer.close()
    print("\nTraining completed!")

if __name__ == "__main__":
    main()
