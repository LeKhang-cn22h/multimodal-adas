# FEAT-dataset-training: Tải Dataset + Train Random Forest Baseline

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-drowsiness-detection.md` — AC-3.3, AC-3.4 (Dataset pipeline)

## Service
**driver-service** — tạo thư mục `training/` chứa script standalone (không nằm trong app runtime)

## Mô tả chức năng

Xây dựng pipeline huấn luyện offline cho Random Forest classifier. Script chạy độc lập (không cần FastAPI app), output là file model `.joblib` và file features `.csv` để phân tích.

### Các bước

```
1. Tải dataset         → NTHU-DDD từ Kaggle mirror (samymesbah/nthu-dataset-ddd-multi-class)
                          qua kagglehub (~360K ảnh .jpg, không phải video)
2. Parse tên file       → Trích xuất subject_id, scenario, frame_number, label từ filename
3. Extract features     → Dùng Face Landmarker trên từng ảnh
                          Trích xuất EAR, MAR, HeadPose (Yaw/Pitch/Roll)
4. Tính PERCLOS         → Group theo (subject, scenario), sort frame_number
                          PERCLOS với sliding window 30s (centered, 900 frames @ 30fps giả định)
5. Tạo feature vector   → [EAR, PERCLOS, MAR, Yaw, Pitch, Roll] + label_binary
6. Lưu CSV              → dataset_features.csv
7. Split train/test     → Theo subject_id (80/20), KHÔNG random theo ảnh
8. Train RF binary      → RandomForestClassifier (n_estimators=100, max_depth=10, class_weight='balanced')
                          predict_proba → Fatigue Score 0-100
                          Map 4 cấp bằng post-processing (không train trực tiếp)
9. Lưu model            → fatigue_rf_model.joblib
10. Báo cáo             → accuracy, f1, confusion matrix heatmap, feature importance bar chart, ROC curve
```

### Dataset details

| Thuộc tính | Giá trị |
|---|---|
| **Tên** | NTHU-DDD (National Tsing Hua University Driver Drowsiness Detection) |
| **Nguồn tải** | Kaggle mirror: `samymesbah/nthu-dataset-ddd-multi-class` qua `kagglehub` |
| **Bản chất** | Re-upload không chính thức. Cần trích dẫn paper gốc (Weng et al., ACCV 2016) trong README |
| **Định dạng** | Ảnh `.jpg` (đã extract từ video gốc) |
| **Cấu trúc** | `Multi class/train/{drowsy,notdrowsy}/{scenario}/*.jpg` — drowsy chia 3 sub: `sleepyCombination`, `slowBlinkWithNodding`, `yawning` |
| **Tên file** | `{subject_id}_{glasses\|noglasses}_{scenario}_{frame_number}_{label}.jpg`, label `_1` = drowsy, `_0` = not drowsy |
| **FPS** | Giả định 30 FPS từ frame_number liên tục (cần note đây là assumption) |
| **Label** | Binary (drowsy/notdrowsy). KHÔNG có mức độ 4 cấp — sẽ map qua post-processing |
| **Train/test split** | Theo `subject_id` (80/20), tránh leak giữa các frame của cùng 1 người |

## Acceptance Criteria

- [ ] **AC-F4.1**: Thư mục `training/` được tạo trong `driver-service/`, chứa:
  - `download_datasets.py` — script tải NTHU-DDD + YawDD (có hướng dẫn nếu cần tải thủ công)
  - `extract_features.py` — chạy Face Landmarker trên toàn bộ video, output CSV
  - `train_model.py` — train Random Forest, lưu `.joblib`, in báo cáo accuracy
  - `requirements.txt` — dependency riêng cho training (scikit-learn, pandas, tqdm...)
  - `README.md` — hướng dẫn từng bước
- [ ] **AC-F4.2**: `extract_features.py` output file `dataset_features.csv` với columns: `subject_id, scenario, frame_number, ear, perclos, mar, yaw, pitch, roll, label_binary` (label_binary: 0=not_drowsy, 1=drowsy). KHÔNG dùng 4-class vì dataset không có nhãn mức độ thật
- [ ] **AC-F4.3**: `train_model.py` output file `fatigue_rf_model.joblib` (≤ 10MB) + báo cáo text `training_report.txt` gồm accuracy, precision/recall/f1 (binary), confusion matrix. Charts: `confusion_matrix.png` (heatmap), `feature_importance.png` (bar chart 6 features), `roc_curve.png` (ROC + AUC)
- [ ] **AC-F4.4**: Random Forest dùng hyperparameters baseline: `n_estimators=100, max_depth=10, random_state=42, class_weight='balanced'`. **Train binary classifier** (drowsy/notdrowsy), không train 4-class. Fatigue Score = `predict_proba(class=1) × 100`, mapping 4 cấp làm ở post-processing (FEAT-fatigue-classifier)
- [ ] **AC-F4.5**: Script có xử lý lỗi: dataset không tồn tại → in hướng dẫn; video corrupt → skip + log; không phát hiện mặt → gán feature = NaN → drop row
- [ ] **AC-F4.6**: `dataset_features.csv` và `fatigue_rf_model.joblib` được lưu trong `training/output/` (gitignore trừ model `.joblib` cuối cùng)
- [ ] **AC-F4.7**: Script chạy được trên môi trường không cần RabbitMQ/FastAPI — chỉ cần `face_landmarker.task` + scikit-learn + opencv

## Độ ưu tiên
**P1** — Có thể làm song song với FEAT-feature-extraction và FEAT-fatigue-classifier (vì script training độc lập, không ảnh hưởng app runtime). Cần hoàn thành trước FEAT-rf-integration.

## Phụ thuộc
- **FEAT-landmark-refactor**: Cần `FaceLandmarkerService` để extract features (hoặc script training tự import trực tiếp)
- **FEAT-feature-extraction**: Cần định nghĩa `FeatureVector` và các hàm MAR/HeadPose/PERCLOS để script training extract đúng 6 features
