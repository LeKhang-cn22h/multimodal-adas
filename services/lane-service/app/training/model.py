import torch
import torch.nn as nn
import torchvision.models.segmentation as segmentation

def get_model(num_classes=3):
    """
    Khoi tao mo hinh DeepLabV3+ voi backbone MobileNetV3 Large de dat toc do chay sieu toc (Real-time).
    """
    try:
        # PyTorch 1.13+ API
        from torchvision.models.segmentation import DeepLabV3_MobileNet_V3_Large_Weights
        weights = DeepLabV3_MobileNet_V3_Large_Weights.DEFAULT
        model = segmentation.deeplabv3_mobilenet_v3_large(weights=weights)
        print("Initialized DeepLabV3 MobileNetV3 Large with pretrained ImageNet weights.")
    except Exception:
        # Fallback cho cac phien ban PyTorch cu hon
        try:
            model = segmentation.deeplabv3_mobilenet_v3_large(pretrained=True)
            print("Initialized DeepLabV3 MobileNetV3 Large with pretrained=True.")
        except Exception:
            model = segmentation.deeplabv3_mobilenet_v3_large(pretrained=False)
            print("Initialized DeepLabV3 MobileNetV3 Large with pretrained=False.")

    # Thay the bo phan phan loai (Classifier Head) cu de phu hop voi so class cua ta (3 classes)
    # Mac dinh model duoc train cho 21 class (Pascal VOC)
    in_channels = model.classifier[4].in_channels
    model.classifier[4] = nn.Conv2d(in_channels, num_classes, kernel_size=1)
    
    # Neu model co auxiliary classifier thi cung cap nhat lai de tranh loi khi train
    if hasattr(model, 'aux_classifier') and model.aux_classifier is not None:
        aux_in_channels = model.aux_classifier[4].in_channels
        model.aux_classifier[4] = nn.Conv2d(aux_in_channels, num_classes, kernel_size=1)

    return model

if __name__ == "__main__":
    # Test thu khoi tao model
    m = get_model(3)
    x = torch.randn(1, 3, 360, 640)
    out = m(x)
    print("Output shape:", out['out'].shape) # Ky vong: (1, 3, 360, 640)
