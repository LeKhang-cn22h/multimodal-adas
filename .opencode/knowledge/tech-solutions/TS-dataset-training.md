# TS-dataset-training: Tải NTHU-DDD + Train Random Forest & XGBoost Baseline

## Thuộc Feature
`.opencode/knowledge/features/FEAT-dataset-training.md`

## Kiến trúc

### Tổng quan

Toàn bộ pipeline nằm trong thư mục `driver-service/training/`, chạy **độc lập** với FastAPI app. Không cần RabbitMQ, không cần uvicorn. Chỉ cần `face_landmarker.task` + các thư viện ML.

**Thay đổi so với thiết kế cũ**: Sử dụng `FaceLandmarkerService` (đã implement trong `app/services/mediapipe_service.py`) thay vì tự tạo MediaPipe pipeline riêng cho training. Đảm bảo train/infer dùng cùng 1 code path → không bị train-serving skew từ khâu landmark extraction.

```
training/
├── download_datasets.py       # Tải NTHU-DDD từ Kaggle mirror qua kagglehub
├── extract_features.py        # Gọi FaceLandmarkerService + tính 7 root features → intermediate CSV
├── engineer_features.py       # Từ intermediate CSV → 40 features (stats + temporal + PERCLOS) → final CSV
├── train_model.py             # Train RF vs XGBoost, so sánh, lưu model tốt nhất
├── requirements.txt           # kagglehub, scikit-learn, xgboost, pandas, matplotlib, seaborn, tqdm, opencv-python, mediapipe, scipy, numpy, joblib
├── README.md                  # Hướng dẫn từng bước
└── output/                    # (gitignore trừ model .pkl)
    ├── dataset_intermediate.csv    # 7 root features per frame (Step 2 output)
    ├── dataset_features.csv        # 40 features đầy đủ (Step 3 output)
    ├── model.pkl                   # Model tốt nhất train trên toàn bộ 4 subject (production)
    ├── rf_model.joblib             # Random Forest production (để so sánh, không dùng runtime)
    ├── xgb_model.json              # XGBoost production (để so sánh, không dùng runtime)
    ├── training_report.txt         # Báo cáo text (LOSO-CV per-fold + so sánh)
    ├── loso_comparison.png         # Bar chart so sánh 4 metrics mean±std (RF vs XGB)
    ├── loso_accuracy_by_subject.png# Bar chart Accuracy từng subject (4 subject × 2 model)
    ├── loso_roc_comparison.png     # ROC curves aggregate (RF + XGB)
    ├── confusion_matrix_rf.png     # Confusion matrix RF (aggregate 4 fold)
    ├── confusion_matrix_xgb.png    # Confusion matrix XGB (aggregate 4 fold)
    ├── feature_importance_rf.png   # Feature importance top-20 (RF production model)
    └── feature_importance_xgb.png  # Feature importance top-20 (XGB production model)
```

### Luồng dữ liệu

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1 — Tải dataset                                                │
│                                                                     │
│  Dataset đã có sẵn (không cần tải):                                   │
│    dataset/Multi class/train/                                        │
│                                                                     │
│  Cấu trúc thực tế (BẤT ĐỐI XỨNG — cần xử lý 2 kiểu duyệt):           │
│    drowsy/                     ← có 3 sub-folder theo scenario       │
│      ├── sleepyCombination/                                         │
│      ├── yawning/                                                   │
│      └── slowBlinkWithNodding/                                      │
│    notdrowsy/                  ← FLAT, KHÔNG có sub-folder           │
│                                                                     │
│  Filename format:                                                   │
│    {subject_id}_{glasses|noglasses}_{scenario}_{frameNumber}_label.jpg
│    VD: 001_glasses_sleepyCombination_1000_drowsy.jpg                 │
│         └─ subject 001, glasses, scenario sleepy, frame 1000, label "drowsy"
│                                                                     │
│  Label mapping (từ suffix cuối cùng trước .jpg):                     │
│    _drowsy.jpg    → drowsy (positive class) → map về int 1          │
│    _notdrowsy.jpg → not drowsy (negative class) → map về int 0      │
│                                                                     │
│  ⚠️ Label trong tên file là CHUỖI "drowsy"/"notdrowsy".             │
│  Script extract_features.py parse chuỗi → map về int 0/1 khi ghi    │
│  CSV (label_binary: int, 0=notdrowsy, 1=drowsy).                    │
│                                                                     │
│  Giả định: 30 FPS (từ frame_number liên tục), cần note rõ trong     │
│  báo cáo đây là assumption chưa được xác nhận từ metadata gốc.      │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 2 — Extract ROOT features per image (dùng FaceLandmarkerService)│
│                                                                     │
│  ⚠️ DÙNG LẠI FaceLandmarkerService đã implement, KHÔNG viết pipeline│
│  MediaPipe riêng. Script training import trực tiếp class này để đảm  │
│  bảo code path landmark extraction giống hệt runtime.               │
│                                                                     │
│  ⚠️ Do cấu trúc thư mục bất đối xứng, cần 2 vòng lặp riêng:         │
│    - drowsy: walk 3 sub-dirs (sleepyCombination, yawning,            │
│      slowBlinkWithNodding) → label_binary = 1, scenario = tên dir   │
│    - notdrowsy: duyệt flat → label_binary = 0, scenario = parse     │
│      từ field thứ 3 trong tên file (giữa glasses và frame_number)    │
│                                                                     │
│  For each .jpg:                                                     │
│    0. Parse tên file: tách subject_id, glasses, scenario,            │
│       frame_number, label_string.                                    │
│       Map label_string → label_binary:                               │
│         "drowsy" → 1, "notdrowsy" → 0                                │
│    1. cv2.imread → BGR                                              │
│    2. Gọi FaceLandmarkerService.detect(frame, timestamp_ms)         │
│       → FaceLandmarkerResult(landmarks, transformation_matrix)      │
│    3. Nếu face_detected == False → skip image (log warning)         │
│    4. Tính EAR_left  = calculate_ear(landmarks, LEFT_EYE)           │
│       từ app.utils.ear                                              │
│    5. Tính EAR_right = calculate_ear(landmarks, RIGHT_EYE)          │
│       từ app.utils.ear                                              │
│    6. Tính EAR_avg   = (EAR_left + EAR_right) / 2                   │
│    7. Tính MAR từ app.utils.mar (phải được implement)               │
│    8. Tính Yaw, Pitch, Roll từ transformation_matrix                │
│       qua app.utils.headpose (phải được implement)                  │
│                                                                     │
│  Output: intermediate CSV với cột:                                   │
│    subject_id (str), scenario (str), frame_number (int),              │
│    ear_left, ear_right, ear_avg, mar, yaw, pitch, roll (float),      │
│    label_binary (int: 0 = not drowsy, 1 = drowsy)                     │
│                                                                     │
│  ⚠️ label_binary là INTEGER 0/1, không phải string.                  │
│  pandas đọc CSV → cột label_binary có dtype int64.                   │
│                                                                     │
│  Đảm bảo sort theo (subject_id, scenario, frame_number) ASC         │
│  trước khi ghi file. Đây là input cho Step 3.                       │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 3 — Engineer FULL features (40 cột)                             │
│                                                                     │
│  Đọc intermediate CSV từ Step 2. Group by (subject_id, scenario),    │
│  sort by frame_number.                                               │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Step 3a — Sliding window STATISTICS (backward, 28 features)        │
│  ═══════════════════════════════════════════════════════════════════│
│                                                                     │
│  ⚠️ BACKWARD window: chỉ nhìn frame QUÁ KHỨ, không peek tương lai.  │
│  Đảm bảo feature khả dụng lúc runtime inference.                    │
│                                                                     │
│  N_stat = 300 frames (10 giây @ 30 FPS)                             │
│                                                                     │
│  Algorithm (trong TỪNG group (subject_id, scenario) riêng biệt):    │
│    Gọi len_g = số frame trong group sau khi sort frame_number ASC.  │
│    i là index CỤC BỘ trong group (i = 0, 1, ..., len_g - 1).       │
│    Cửa sổ reset khi chuyển sang group mới.                          │
│                                                                     │
│    For each root feature F in {ear_left, ear_right, ear_avg, mar,   │
│    yaw, pitch, roll}:                                               │
│      For i in range(len_g):                                         │
│        if i < N_stat - 1:  → SKIP (cửa sổ chưa đủ, bỏ frame này)   │
│        start = i - N_stat + 1              ← backward: [i-N_stat+1, i]│
│        window = F_series.iloc[start : i+1]                         │
│        F_mean = np.mean(window)                                     │
│        F_std  = np.std(window, ddof=1)                              │
│        F_min  = np.min(window)                                      │
│        F_max  = np.max(window)                                      │
│                                                                     │
│  ⚠️ KHÔNG dùng expanding window. Các frame i < N_stat - 1 bị LOẠI   │
│  BỎ hoàn toàn khỏi dataset (xem chi tiết ở mục "Xử lý frame đầu     │
│  thiếu cửa sổ" bên dưới).                                           │
│                                                                     │
│  → 7 features × 4 statistics = 28 features                          │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Step 3b — PERCLOS (backward window, 1 feature)                     │
│  ═══════════════════════════════════════════════════════════════════│
│                                                                     │
│  ⚠️ TÍNH Y HỆT CÁCH LÀM LÚC RUNTIME TRONG DRIVER-SERVICE.           │
│  Dùng BACKWARD window: chỉ nhìn frame QUÁ KHỨ, không peek tương lai.│
│                                                                     │
│  N_perclos = 900 frames (30 giây @ 30 FPS)                          │
│  EAR_THRESHOLD: import từ `app.core.config.get_settings().EAR_THRESHOLD`│
│  (giá trị mặc định 0.22, đồng nhất với runtime).                    │
│                                                                     │
│  Algorithm (trong TỪNG group (subject_id, scenario), i là index     │
│  CỤC BỘ trong group):                                               │
│    for i in range(len_g):                                           │
│      if i < N_perclos - 1:  → SKIP (cửa sổ chưa đủ, bỏ frame này)  │
│      start = i - N_perclos + 1             ← backward: [i-N+1, i]   │
│      window = ear_avg.iloc[start : i+1]                             │
│      PERCLOS = 100.0 * count(ear_avg < EAR_THRESHOLD) / len(window) │
│                                                                     │
│  ⚠️ KHÔNG dùng expanding window. Các frame i < N_perclos - 1 bị     │
│  LOẠI BỎ hoàn toàn khỏi dataset.                                   │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Step 3c — Temporal/behavioral features (5 features)                │
│  ═══════════════════════════════════════════════════════════════════│
│                                                                     │
│  Mọi vòng lặp dưới đây chạy trong TỪNG group (subject_id, scenario) │
│  riêng biệt, i là index CỤC BỘ trong group.                         │
│  EAR_THRESHOLD import từ `app.core.config`.                         │
│                                                                     │
│  blink_rate (backward window, 1 feature):                           │
│    Dùng N_blink = 900 frames (30 giây).                             │
│    Với mỗi i >= N_blink - 1:                                        │
│      window = ear_avg.iloc[i - N_blink + 1 : i + 1]                 │
│      Duyệt ear_avg trong window, đếm số lần ear_avg cắt ngưỡng      │
│      EAR_THRESHOLD từ trên xuống dưới (blink onset). Yêu cầu:       │
│      2 blink liên tiếp cách nhau ≥ 5 frame (200ms) để tránh         │
│      double-count do dao động ở biên.                               │
│      blink_rate = n_blinks / (window_duration_seconds / 60.0)       │
│      → Đơn vị: blinks/phút.                                         │
│    Với i < N_blink - 1: → SKIP (bỏ frame, không impute).           │
│                                                                     │
│  yaw_velocity (1 feature):                                          │
│    Dùng N_vel = 30 frames (1 giây).                                 │
│    Với mỗi i >= N_vel - 1:                                          │
│      yaw_window = yaw.iloc[i - N_vel + 1 : i + 1]                   │
│      yaw_velocity = np.mean(np.abs(np.diff(yaw_window))) * 30       │
│      → Đơn vị: deg/s.                                               │
│    Với i < N_vel - 1: → SKIP (bỏ frame).                           │
│                                                                     │
│  pitch_velocity (1 feature):                                        │
│    Với mỗi i >= N_vel - 1:                                          │
│      pitch_window = pitch.iloc[i - N_vel + 1 : i + 1]               │
│      pitch_velocity = np.mean(np.abs(np.diff(pitch_window))) * 30   │
│    Với i < N_vel - 1: → SKIP.                                       │
│                                                                     │
│  roll_velocity (1 feature):                                         │
│    Với mỗi i >= N_vel - 1:                                          │
│      roll_window = roll.iloc[i - N_vel + 1 : i + 1]                 │
│      roll_velocity = np.mean(np.abs(np.diff(roll_window))) * 30     │
│    Với i < N_vel - 1: → SKIP.                                       │
│                                                                     │
│  ⚠️ KHÔNG dùng expanding window. Các frame không đủ cửa sổ bị LOẠI  │
│  BỎ hoàn toàn khỏi dataset.                                        │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Step 3d — Xử lý frame đầu thiếu cửa sổ (CUT-OFF)                  │
│  ═══════════════════════════════════════════════════════════════════│
│                                                                     │
│  Ngưỡng cut-off: N_cutoff = N_perclos - 1 = 899.                    │
│  (Chọn cửa sổ lớn nhất trong tất cả feature làm ngưỡng chung.       │
│   N_perclos=900 > N_stat=300 > N_vel=30.)                           │
│                                                                     │
│  Trong mỗi group (subject_id, scenario):                            │
│    Chỉ giữ lại frame có index cục bộ i >= N_cutoff.                 │
│    Các frame i < N_cutoff bị LOẠI BỎ — không expanding window,      │
│    không impute (fillna), không forward-fill.                       │
│                                                                     │
│  Ước tính số dòng bị loại:                                          │
│    ≈ 900 × n_groups                                                  │
│    Với n_groups = số cặp (subject_id, scenario) duy nhất.           │
│    Log con số THẬT (n_groups, total_dropped, pct_dropped) khi       │
│    chạy engineer_features.py.                                       │
│                                                                     │
│  Tổng kết feature: 7 root + 28 stats + 1 PERCLOS + 1 blink_rate     │
│  + 3 velocities = 40 features.                                      │
│                                                                     │
│  Output: final CSV — dataset_features.csv với columns:              │
│    subject_id (str), scenario (str), frame_number (int),              │
│    [40 feature columns — xem danh sách đầy đủ ở mục "Danh sách      │
│     feature cuối cùng" bên dưới],                                    │
│    label_binary (int), label_smoothed (int)                          │
│                                                                     │
│  Cả 2 cột label đều là INTEGER: 0 = not drowsy, 1 = drowsy.         │
│  label_smoothed có cùng dtype với label_binary (int64),              │
│  chỉ khác giá trị ở biên chuyển trạng thái.                          │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 4 — Smooth LABEL (centered window, ONLY for ground-truth)      │
│                                                                     │
│  ⚠️ CENTERED window CHỈ dùng để làm mượt NHÃN (label), KHÔNG dùng   │
│  để tính giá trị feature. Mục đích: xử lý các frame nằm gần ranh    │
│  giới chuyển trạng thái (VD: đoạn "notdrowsy" chuyển sang           │
│  "drowsy"), tránh label bị nhiễu ở biên.                            │
│                                                                     │
│  Thực hiện trong TỪNG group (subject_id, scenario), i là index      │
│  CỤC BỘ trong group sau sort frame_number ASC:                      │
│    start = max(0, i - LABEL_SMOOTH // 2)     ← centered window       │
│    end = min(len(group), i + LABEL_SMOOTH // 2)                     │
│    majority_label = mode(group.iloc[start:end]['label_binary'])     │
│    group.at[i, 'label_smoothed'] = majority_label                   │
│                                                                     │
│  LABEL_SMOOTH = 30 frames (1 giây @ 30fps) — cửa sổ đủ nhỏ để chỉ   │
│  làm mượt biên, không làm mất tín hiệu chuyển trạng thái thật.      │
│                                                                     │
│  ⚠️ Dùng label_smoothed làm ground-truth để train.                  │
│  ⚠️ Nếu subject+scenario chỉ có 1 loại label → skip smoothing       │
│     (không có biên để làm mượt).                                    │
│                                                                     │
│  Số frame bị thay đổi label do smoothing: dự kiến < 2%, cần log     │
│  chính xác trong training_report.txt.                               │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 5 — Leave-One-Subject-Out Cross-Validation (LOSO-CV)           │
│                                                                     │
│  ❌ KHÔNG split ngẫu nhiên theo ảnh (data leak!)                    │
│  ❌ KHÔNG split 80/20 theo subject_id (4 subject quá ít cho 1 split) │
│  ✅ LOSO-CV: mỗi vòng lặp để 1 subject làm test, các subject còn    │
│     lại làm train — lặp qua TOÀN BỘ subject.                        │
│                                                                     │
│  Dataset thực tế (khảo sát 2026-07-05): 4 subject                   │
│    subject_id = {001, 002, 005, 006}                                │
│                                                                     │
│  Số fold = 4 (mỗi fold = 1 subject test, 3 subjects train):         │
│    Fold 1: test=001, train={002, 005, 006}                          │
│    Fold 2: test=002, train={001, 005, 006}                          │
│    Fold 3: test=005, train={001, 002, 006}                          │
│    Fold 4: test=006, train={001, 002, 005}                          │
│                                                                     │
│  Lưu ý: tất cả frame của cùng 1 subject nằm TRỌN trong train HOẶC   │
│  test của 1 fold, không bị trộn lẫn.                                │
│                                                                     │
│  ⚠️ 4 model tạm thời trong vòng lặp LOSO-CV CHỈ dùng để đánh giá,   │
│  KHÔNG lưu ra file. Model production (model.pkl) được train riêng    │
│  ở Step 6b trên TOÀN BỘ 4 subject.                                  │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 6 — Train & Compare: RandomForest vs XGBoost (LOSO-CV)         │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Model A: RandomForestClassifier (sklearn)                          │
│  ═══════════════════════════════════════════════════════════════════│
│    n_estimators = 100                                               │
│    max_depth = 10                                                   │
│    random_state = 42                                                │
│    class_weight = 'balanced'                                        │
│    n_jobs = -1                                                      │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Model B: XGBClassifier (xgboost)                                   │
│  ═══════════════════════════════════════════════════════════════════│
│    n_estimators = 100                                               │
│    max_depth = 6                                                    │
│    learning_rate = 0.1                                              │
│    random_state = 42                                                │
│    scale_pos_weight = n_negative / n_positive  (auto-balance)      │
│    eval_metric = 'logloss'                                          │
│    use_label_encoder = False                                        │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Step 6a — LOSO-CV (đánh giá, 4 fold × 2 model = 8 lần train)     │
│  ═══════════════════════════════════════════════════════════════════│
│                                                                     │
│  For each model_type in {RandomForest, XGBoost}:                    │
│    For each test_subject in {001, 002, 005, 006}:                   │
│      train_subjects = all_subjects - {test_subject}                 │
│      X_train = tất cả frame của train_subjects (40 features)        │
│      y_train = label_smoothed của train_subjects                    │
│      X_test  = tất cả frame của test_subject   (40 features)        │
│      y_test  = label_smoothed của test_subject                      │
│                                                                     │
│      model.fit(X_train, y_train)                                    │
│      y_pred = model.predict(X_test)                                 │
│                                                                     │
│      # Lấy xác suất class drowsy (label=1, index=1).                │
│      # Vì label_binary là int 0/1 nên model.classes_ = [0, 1],     │
│      # drowsy luôn ở index 1. DÙNG model.classes_ ĐỂ XÁC MINH:     │
│      drowsy_idx = list(model.classes_).index(1)                     │
│      y_proba = model.predict_proba(X_test)[:, drowsy_idx]           │
│                                                                     │
│      Metrics cho fold này:                                          │
│        Accuracy, Precision, Recall, F1 (class drowsy), ROC-AUC      │
│      Lưu vào bảng per-fold. Model fold KHÔNG lưu ra file.          │
│                                                                     │
│  Đầu ra bảng per-fold (cho mỗi model):                              │
│                                                                     │
│    Fold | Test Subject | #Train | #Test | Acc | F1  | Recall | AUC  │
│    ─────┼──────────────┼────────┼───────┼─────┼─────┼────────┼───── │
│    1    | 001          | ...    | ...   | ... | ... | ...    | ...  │
│    2    | 002          | ...    | ...   | ... | ... | ...    | ...  │
│    3    | 005          | ...    | ...   | ... | ... | ...    | ...  │
│    4    | 006          | ...    | ...   | ... | ... | ...    | ...  │
│    ─────┼──────────────┼────────┼───────┼─────┼─────┼────────┼───── │
│    Mean ± Std          |        |       | μ±σ | μ±σ | μ±σ    | μ±σ  │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Tiêu chí chọn model (dựa trên kết quả LOSO-CV)                    │
│  ═══════════════════════════════════════════════════════════════════│
│  So sánh mean ROC-AUC qua 4 fold giữa RF và XGB:                   │
│    - Chính: mean ROC-AUC cao hơn                                    │
│    - Phụ (nếu chênh < 0.01): mean F1-score cao hơn                  │
│      (ưu tiên model cân bằng precision/recall khi class imbalance)   │
│  → Chọn model_type thắng để train production model ở Step 6b.      │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Step 6b — Train PRODUCTION model (trên TOÀN BỘ 4 subject)         │
│  ═══════════════════════════════════════════════════════════════════│
│                                                                     │
│  ⚠️ ĐÂY LÀ MODEL THẬT DÙNG TRONG DRIVER-SERVICE PRODUCTION.         │
│  KHÔNG phải model từ vòng LOSO-CV (vốn chỉ để đánh giá).            │
│                                                                     │
│  Dùng model_type đã chọn ở Step 6a.                                │
│  Train 1 lần duy nhất trên TOÀN BỘ dữ liệu (all 4 subjects):       │
│    X_all = tất cả frame của {001, 002, 005, 006} (40 features)     │
│    y_all = label_smoothed của toàn bộ 4 subject                     │
│    model.fit(X_all, y_all)                                          │
│                                                                     │
│  Lưu model: joblib.dump(model, "output/model.pkl")                  │
│  → Đây là file duy nhất được load bởi driver-service runtime.      │
│                                                                     │
│  ⚠️ KHÔNG có test set cho model này — độ tin cậy đã được đánh giá   │
│  qua LOSO-CV ở Step 6a.                                            │
│                                                                     │
│  ═══════════════════════════════════════════════════════════════════│
│  Biểu đồ xuất ra                                                    │
│  ═══════════════════════════════════════════════════════════════════│
│  ⚠️ VẪN xuất biểu đồ SO SÁNH CẢ 2 MODEL:                           │
│    - loso_comparison.png: grouped bar chart (4 metrics mean±std     │
│      cho RF vs XGB, dùng error bar là std qua 4 fold)               │
│    - loso_accuracy_by_subject.png: bar chart Accuracy từng fold     │
│      (4 subject × 2 model), trục X = subject_id                     │
│    - loso_roc_comparison.png: 2 đường ROC (RF vs XGB) aggregate     │
│      từ toàn bộ prediction các fold                                  │
│    - confusion_matrix_rf.png: aggregate confusion matrix RF         │
│      (gộp prediction từ cả 4 fold)                                  │
│    - confusion_matrix_xgb.png: aggregate confusion matrix XGB       │
│    - feature_importance_rf.png: feature importance từ model         │
│      production (Step 6b), top-20                                   │
│    - feature_importance_xgb.png: feature importance từ model        │
│      production (Step 6b), top-20                                   │
│                                                                     │
│  Model size ước tính:                                               │
│    - RF: ≤ 10MB (100 trees × depth 10)                              │
│    - XGB: ≤ 5MB (100 trees × depth 6)                               │
│                                                                     │
│  ⚠️ Train BINARY classifier, KHÔNG train 4-class:                   │
│    - Dataset chỉ có nhãn drowsy/notdrowsy, không có mức độ thật     │
│    - Dùng predict_proba để lấy xác suất drowsy (class 1)            │
│    - Score = proba_drowsy × 100  → Fatigue Score liên tục 0-100     │
│    - Áp ngưỡng post-processing để map về 4 cấp (làm ở FEAT-fatigue-  │
│      classifier, không phải ở đây)                                  │
└─────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 7 — Generate report                                            │
│                                                                     │
│  training_report.txt:                                               │
│    - Số subject tổng (4) và danh sách subject                       │
│    - Số nhóm (subject_id, scenario) và số frame bị cut-off           │
│    - Bảng per-fold chi tiết cho RF (4 dòng + dòng Mean±Std)         │
│    - Bảng per-fold chi tiết cho XGB (4 dòng + dòng Mean±Std)        │
│    - Kết luận: model nào thắng, lý do (ROC-AUC mean ± std)          │
│    - Model được chọn + hyperparams                                  │
│    - Số frame bị thay đổi label do smoothing                        │
│    - Ghi chú limitation: dataset 4 subject, độ tin cậy hạn chế      │
│                                                                     │
│  Charts (PNG):                                                      │
│    - loso_comparison.png: grouped bar chart so sánh 4 metrics        │
│      (Accuracy, F1, Recall, ROC-AUC) mean±std cho RF vs XGB         │
│    - loso_accuracy_by_subject.png: bar chart Accuracy từng fold     │
│      (4 subject × 2 model), trục X = subject_id                     │
│    - loso_roc_comparison.png: 2 ROC curves aggregate + AUC          │
│    - confusion_matrix_rf.png: aggregate confusion matrix RF         │
│    - confusion_matrix_xgb.png: aggregate confusion matrix XGB       │
│    - feature_importance_rf.png: bar chart top-20 features (từ       │
│      production model, Step 6b)                                      │
│    - feature_importance_xgb.png: bar chart top-20 features (từ      │
│      production model, Step 6b)                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Danh sách feature cuối cùng (40 cột)

> ⚠️ **Tất cả statistical & temporal features dùng BACKWARD window** (trừ label_smoothed dùng centered). Mục đích: đảm bảo feature khả dụng lúc runtime inference, không peek tương lai.
> 
> ⚠️ **Quy tắc index**: `i` trong mọi công thức bên dưới là index CỤC BỘ trong từng group (subject_id, scenario) sau khi sort frame_number ASC. Cửa sổ reset khi sang group mới.
> 
> ⚠️ **Quy tắc cut-off**: Các frame có `i < 899` (N_perclos - 1) bị LOẠI BỎ hoàn toàn khỏi dataset. Không expanding window, không impute. Số nhóm (subject_id, scenario) duy nhất và số dòng bị loại được log khi chạy engineer_features.py.

#### A. Root features (7) — từ Step 2, per-frame

| # | Tên cột | Công thức | Window |
|---|---|---|---|
| 1 | `ear_left` | `calculate_ear(landmarks, LEFT_EYE)` từ `app.utils.ear` | — |
| 2 | `ear_right` | `calculate_ear(landmarks, RIGHT_EYE)` từ `app.utils.ear` | — |
| 3 | `ear_avg` | `(ear_left + ear_right) / 2.0` | — |
| 4 | `mar` | `calculate_mar(landmarks)` từ `app.utils.mar` | — |
| 5 | `yaw` | Euler Yaw (độ) từ transformation_matrix qua `app.utils.headpose` | — |
| 6 | `pitch` | Euler Pitch (độ) từ transformation_matrix qua `app.utils.headpose` | — |
| 7 | `roll` | Euler Roll (độ) từ transformation_matrix qua `app.utils.headpose` | — |

#### B. Sliding window statistics (28) — từ Step 3a, backward window

> ⚠️ Mọi công thức dưới đây tính trong TỪNG group (subject_id, scenario) riêng biệt.
> `i` là index CỤC BỘ trong group sau khi sort frame_number ASC.
> Chỉ tính cho frame có `i >= N_stat - 1` (= 299). Các frame `i < 299` bị LOẠI BỎ.
> `start = i - N_stat + 1`, window = `F_series.iloc[start : i+1]` (N_stat phần tử).

| # | Tên cột | Công thức | Window |
|---|---|---|---|
| 8 | `ear_left_mean` | `np.mean(window)` | N=300 backward |
| 9 | `ear_left_std` | `np.std(window, ddof=1)` | N=300 backward |
| 10 | `ear_left_min` | `np.min(window)` | N=300 backward |
| 11 | `ear_left_max` | `np.max(window)` | N=300 backward |
| 12 | `ear_right_mean` | `np.mean(window)` | N=300 backward |
| 13 | `ear_right_std` | `np.std(window, ddof=1)` | N=300 backward |
| 14 | `ear_right_min` | `np.min(window)` | N=300 backward |
| 15 | `ear_right_max` | `np.max(window)` | N=300 backward |
| 16 | `ear_avg_mean` | `np.mean(window)` | N=300 backward |
| 17 | `ear_avg_std` | `np.std(window, ddof=1)` | N=300 backward |
| 18 | `ear_avg_min` | `np.min(window)` | N=300 backward |
| 19 | `ear_avg_max` | `np.max(window)` | N=300 backward |
| 20 | `mar_mean` | `np.mean(window)` | N=300 backward |
| 21 | `mar_std` | `np.std(window, ddof=1)` | N=300 backward |
| 22 | `mar_min` | `np.min(window)` | N=300 backward |
| 23 | `mar_max` | `np.max(window)` | N=300 backward |
| 24 | `yaw_mean` | `np.mean(window)` | N=300 backward |
| 25 | `yaw_std` | `np.std(window, ddof=1)` | N=300 backward |
| 26 | `yaw_min` | `np.min(window)` | N=300 backward |
| 27 | `yaw_max` | `np.max(window)` | N=300 backward |
| 28 | `pitch_mean` | `np.mean(window)` | N=300 backward |
| 29 | `pitch_std` | `np.std(window, ddof=1)` | N=300 backward |
| 30 | `pitch_min` | `np.min(window)` | N=300 backward |
| 31 | `pitch_max` | `np.max(window)` | N=300 backward |
| 32 | `roll_mean` | `np.mean(window)` | N=300 backward |
| 33 | `roll_std` | `np.std(window, ddof=1)` | N=300 backward |
| 34 | `roll_min` | `np.min(window)` | N=300 backward |
| 35 | `roll_max` | `np.max(window)` | N=300 backward |

#### C. Temporal/behavioral features (5) — từ Step 3b + 3c, backward window

> ⚠️ Mọi công thức dưới đây tính trong TỪNG group (subject_id, scenario) riêng biệt.
> `i` là index CỤC BỘ trong group. `EAR_THRESHOLD` import từ `app.core.config`.
> Chỉ tính cho frame có `i >= N_cutoff` (= 899). Các frame `i < 899` bị LOẠI BỎ.

| # | Tên cột | Công thức | Window |
|---|---|---|---|
| 36 | `perclos` | `100.0 * (ear_avg_window < EAR_THRESHOLD).mean()`, ear_avg_window = `ear_avg.iloc[i-899 : i+1]` | N=900 backward (30s) |
| 37 | `blink_rate` | `n_blinks / (T_sec / 60.0)`. n_blinks = số lần `ear_avg` cắt `EAR_THRESHOLD` từ trên xuống trong window `ear_avg.iloc[i-899 : i+1]`, 2 blink liên tiếp cách ≥ 5 frame | N=900 backward (30s) |
| 38 | `yaw_velocity` | `np.mean(np.abs(np.diff(yaw.iloc[i-29 : i+1]))) * 30` | N=30 backward (1s) |
| 39 | `pitch_velocity` | `np.mean(np.abs(np.diff(pitch.iloc[i-29 : i+1]))) * 30` | N=30 backward (1s) |
| 40 | `roll_velocity` | `np.mean(np.abs(np.diff(roll.iloc[i-29 : i+1]))) * 30` | N=30 backward (1s) |

> **Tổng**: 7 root + 28 stats + 5 temporal = **40 features**.
> Sau cut-off (loại frame i < 899 mỗi group): số dòng còn lại ≈ tổng_dòng_gốc - 900 × n_groups.

### File sẽ tạo/sửa

| File | Hành động | Mô tả |
|---|---|---|
| `training/download_datasets.py` | **SKIP** | Dataset đã có sẵn tại `dataset/Multi class/train/`. Không cần script tải. |
| `training/extract_features.py` | **TẠO MỚI** | Import `FaceLandmarkerService`, gọi detect → extract 7 root features → output `dataset_intermediate.csv` |
| `training/engineer_features.py` | **TẠO MỚI** | Đọc intermediate CSV → tính 28 stats (N=300) + PERCLOS + blink_rate + 3 velocities → label smoothing → **cut-off frame i < 899 mỗi group** → log `(n_groups, total_dropped, pct_dropped)` → output `dataset_features.csv` |
| `training/train_model.py` | **TẠO MỚI** | Đọc final CSV → LOSO-CV 4 fold cho RF + XGB → so sánh mean±std → chọn model → train production model trên toàn bộ 4 subject → lưu `model.pkl` + all charts |
| `training/requirements.txt` | **TẠO MỚI** | `scikit-learn`, `xgboost`, `pandas`, `matplotlib`, `seaborn`, `tqdm`, `numpy`, `joblib`. (Các thư viện `opencv-python`, `mediapipe`, `scipy` đã có trong `driver-service/requirements.txt`) |
| `training/README.md` | **TẠO MỚI** | Hướng dẫn: cài deps → chạy extract → engineer → train → output. Bỏ bước download (dataset đã có). |
| `app/utils/mar.py` | **ĐÃ CÓ** | `calculate_mar` — đã implement, không cần stub. |
| `app/utils/headpose.py` | **ĐÃ CÓ** | `extract_head_pose` — đã implement, không cần stub. |
| `app/core/config.py` | **ĐỌC (import)** | Script training import `EAR_THRESHOLD` từ `get_settings().EAR_THRESHOLD`. Dùng chung giá trị này cho PERCLOS và blink_rate, đảm bảo đồng nhất với runtime. Các tham số khác (N_stat, N_perclos, N_vel...) do script training tự define, không cần thêm vào config. |
| `app/services/mediapipe_service.py` | **ĐỌC (import)** | Script training import `FaceLandmarkerService` và `FaceLandmarkerResult` trực tiếp. |

> ⚠️ **Phụ thuộc cứng**: `extract_features.py` cần import từ `app.utils.mar` và `app.utils.headpose`. Nếu 2 file này chưa được implement (hiện đang là file rỗng), script training PHẢI tự define stub function và log warning rõ ràng. Khuyến nghị: hoàn thành `mar.py` và `headpose.py` trước khi chạy training.

### Dependency graph

```
training/scripts (standalone, chạy trong driver-service/, import từ app/)
    ├── face_landmarker.task          (model binary, đã có)
    ├── app.services.mediapipe_service (FaceLandmarkerService — đã implement)
    ├── app.utils.ear                 (import calculate_ear, LEFT_EYE, RIGHT_EYE)
    ├── app.utils.mar                 (import calculate_mar — đã implement)
    ├── app.utils.headpose            (import extract_head_pose — đã implement)
    ├── dataset/Multi class/train/    (dataset đã có sẵn, không cần tải)
    ├── scikit-learn                  (train RF)
    └── xgboost                       (train XGB)
```

## Logic + AI

### Dataset

| Thuộc tính | Giá trị |
|---|---|
| **Tên** | NTHU-DDD (National Tsing Hua University Driver Drowsiness Detection) |
| **Nguồn tải** | Kaggle mirror: `samymesbah/nthu-dataset-ddd-multi-class` qua `kagglehub` |
| **Bản chất** | Re-upload không chính thức. Paper gốc: "Driver Drowsiness Detection via a Hierarchical Temporal Deep Belief Network", Weng et al., ACCV 2016 |
| **License** | Research only — cần trích dẫn paper gốc trong README + báo cáo |
| **Định dạng** | Ảnh `.jpg` (không phải video), đã được extract từ video gốc |
| **Số lượng** | Multi-class: ~360K ảnh (sẽ log chính xác sau khi tải) |
| **Cấu trúc thư mục** | **Bất đối xứng**: `drowsy/` có 3 sub-dir (`sleepyCombination`, `slowBlinkWithNodding`, `yawning`); `notdrowsy/` flat — scenario nằm trong tên file. Script cần 2 vòng lặp riêng để duyệt. |
| **Tên file** | `{subject_id}_{glasses\|noglasses}_{scenario}_{frameNumber}_label.jpg` — VD: `001_glasses_sleepyCombination_1000_drowsy.jpg` |
| **Label** | String trong tên file: suffix `_drowsy.jpg` / `_notdrowsy.jpg`. Script map về int: **0 = not drowsy, 1 = drowsy** khi ghi CSV. |
| **FPS giả định** | 30 FPS (từ frame_number liên tục). ⚠️ Đây là **assumption**, metadata gốc không confirm. Cần note trong báo cáo. |
| **Số subject** | **4 subject**: `001, 002, 005, 006` (khảo sát thực tế 2026-07-05) |
| **Train/test split** | **LOSO-CV** (Leave-One-Subject-Out): 4 fold, mỗi fold 1 subject test, 3 subjects train. KHÔNG split 80/20 vì 4 subject quá ít. Production model train trên toàn bộ 4 subject sau khi đánh giá. |

### Feature Extraction (per frame, Step 2)

| Feature | Công thức | Input | Output |
|---|---|---|---|
| **EAR_left** | `calculate_ear(landmarks, LEFT_EYE)` | 478 landmarks, indices `[33,160,158,133,153,144]` | float (0.05–0.45) |
| **EAR_right** | `calculate_ear(landmarks, RIGHT_EYE)` | 478 landmarks, indices `[362,385,387,263,373,380]` | float (0.05–0.45) |
| **EAR_avg** | `(EAR_left + EAR_right) / 2` | EAR_left, EAR_right | float (0.05–0.45) |
| **MAR** | `calculate_mar(landmarks)` từ `app.utils.mar` | 478 landmarks | float (0.0–1.0) |
| **Yaw** | Euler từ rotation submatrix của transformation_matrix | 4×4 matrix | độ (-90°–90°) |
| **Pitch** | Euler từ rotation submatrix của transformation_matrix | 4×4 matrix | độ (-90°–90°) |
| **Roll** | Euler từ rotation submatrix của transformation_matrix | 4×4 matrix | độ (-90°–90°) |

### PERCLOS Feature Calculation (chi tiết, Step 3b)

```
⚠️ BACKWARD sliding window — Y HỆT cách tính lúc runtime trong driver-service.
Mục đích: đảm bảo không có train-serving skew.

Input:  DataFrame đã sort theo (subject_id, scenario, frame_number)
        Cột ear_avg đã được tính ở Step 2
        EAR_THRESHOLD import từ app.core.config.get_settings().EAR_THRESHOLD

Algorithm:
  for each group (subject_id, scenario):     ← i reset về 0 mỗi group
      for i in range(len(group)):
          if i < WINDOW - 1:                  ← SKIP: cửa sổ chưa đủ
              continue
          start = i - WINDOW + 1              # backward: chỉ frame quá khứ
          window = group.iloc[start : i + 1]   # [i-W+1, i], đúng WINDOW phần tử
          perclos = 100.0 * (window['ear_avg'] < EAR_THRESHOLD).mean()
          group.at[i, 'perclos'] = perclos

  WINDOW = 900  # 30 giây × 30 FPS

  ⚠️ KHÔNG expanding window. Các frame i < WINDOW - 1 (= 899) bị LOẠI BỎ
  sau khi tính xong toàn bộ feature (Step 3d).
```


### Label Smoothing (chi tiết, Step 4)

```
⚠️ CENTERED window — CHỈ dùng cho ground-truth LABEL, KHÔNG cho feature.
Mục đích: làm mượt nhãn ở ranh giới chuyển trạng thái, tránh label noise ở biên.

Input:  DataFrame từ Step 3 (đã có PERCLOS + tất cả feature + label_binary gốc)

Algorithm:
  LABEL_WINDOW = 30  # 1 giây @ 30fps, đủ nhỏ để không làm mất tín hiệu thật

  for each group (subject_id, scenario):
      if group chỉ có 1 loại label → skip smoothing (không có biên)
      for i in range(len(group)):
          start = max(0, i - LABEL_WINDOW // 2)       # centered
          end = min(len(group), i + LABEL_WINDOW // 2)
          labels_in_window = group.iloc[start:end]['label_binary']
          majority = mode(labels_in_window)
          group.at[i, 'label_smoothed'] = majority

  Output: label_smoothed là ground-truth dùng để train RF và XGBoost.
  Feature KHÔNG bị ảnh hưởng bởi bước này — vẫn là backward window.
```

### Model Training (Step 6)

| Thuộc tính | Giá trị |
|---|---|
| **Model A** | `sklearn.ensemble.RandomForestClassifier` |
| **RF Hyperparams** | `n_estimators=100, max_depth=10, random_state=42, class_weight='balanced', n_jobs=-1` |
| **Model B** | `xgboost.XGBClassifier` |
| **XGB Hyperparams** | `n_estimators=100, max_depth=6, learning_rate=0.1, random_state=42, scale_pos_weight=auto, eval_metric='logloss'` |
| **Input** | `X`: numpy array `(n_frames, 40)` — toàn bộ 40 feature columns |
| **Output** | `y`: numpy array `(n_frames,)`, binary 0 (not drowsy) / 1 (drowsy) |
| **Classification type** | **Binary** (không multi-class 4 cấp) |
| **Đánh giá** | **LOSO-CV 4 fold**: mỗi fold 1 subject test, 3 subjects train. Metrics báo cáo dạng mean ± std qua 4 fold + bảng chi tiết từng fold. |
| **Fatigue Score** | `proba_drowsy = model.predict_proba(X)[:, drowsy_idx]` (trong đó `drowsy_idx = list(model.classes_).index(1)` — label 1 = drowsy) → `score = int(proba_drowsy * 100)` |
| **4-cấp mapping** | **Post-processing ở app runtime** (FEAT-fatigue-classifier), không train trực tiếp: `0-25 → Awake, 26-50 → Tired, 51-75 → Drowsy, 76-100 → Dangerous` |
| **Selection criteria** | So sánh mean ROC-AUC qua 4 fold (primary); nếu chênh < 0.01 → chọn theo mean F1-score. |
| **Production model** | **Train lại trên TOÀN BỘ 4 subject** sau khi chọn model type thắng. Model LOSO-CV không lưu. |
| **Save format** | `joblib.dump(production_model, "output/model.pkl")` — load bởi driver-service runtime. RF production lưu thêm `rf_model.joblib`, XGB production lưu thêm `xgb_model.json` để báo cáo. |

### Ngưỡng (Threshold) & Window sizes

| Tham số | Giá trị | Lý do |
|---|---|---|
| `EAR_THRESHOLD` | `0.22` (import từ `app.core.config`) | Literature standard (Soukupova & Cech, 2016). Dùng cho PERCLOS + blink detection. Import trực tiếp, không hardcode riêng trong script training. |
| `N_stat` (stats window) | `300` frames (10 giây) | Đủ dài để bắt medium-term pattern, đủ ngắn để responsive |
| `N_perclos` (PERCLOS window) | `900` frames (30 giây) | Cân bằng giữa responsiveness và stability |
| `N_vel` (velocity window) | `30` frames (1 giây) | Đủ để smooth frame-to-frame noise |
| `N_blink` (blink_rate window) | `900` frames (30 giây) | Cùng cửa sổ PERCLOS để nhất quán |
| `LABEL_SMOOTH` | `30` frames (1 giây) | Chỉ làm mượt biên, không làm mất tín hiệu thật |
| `FPS_ASSUMPTION` | `30` | Giả định từ frame_number liên tục trong NTHU-DDD |
| `LOSO_CV_FOLDS` | `4` (1 fold / subject) | Dataset chỉ có 4 subject (001, 002, 005, 006). Mỗi fold để 1 subject làm test. |

### Hiệu năng ước tính

| Chỉ số | Giá trị | Ghi chú |
|---|---|---|
| **Download time** | 10-30 phút | Phụ thuộc bandwidth, dataset ~2-5GB |
| **Feature extraction time** | 2-6 giờ | ~360K ảnh × ~15ms MediaPipe inference/ảnh = ~90 phút compute + I/O overhead |
| **Feature engineering time** | 5-15 phút | Pure pandas/numpy, không gọi AI |
| **Training time (RF)** | 1-5 phút | 100 trees |
| **Training time (XGB)** | 2-10 phút | 100 estimators, có GPU support nếu có |
| **Inference time** | <1ms/frame | Cả RF lẫn XGB đều rất nhanh |

## API Contract

**Không có API.** Feature này là pipeline training standalone, không expose HTTP endpoint, không đụng tới RabbitMQ. Script chạy từ command line:

```bash
cd training/
pip install -r requirements.txt
python download_datasets.py
python extract_features.py
python engineer_features.py
python train_model.py
```

Đầu ra: `output/model.pkl` được copy ra root `driver-service/` hoặc giữ trong `training/output/` để `FEAT-rf-integration` load.

## Rủi ro & câu hỏi mở

### Rủi ro

| Rủi ro | Mức độ | Giảm thiểu |
|---|---|---|
| **FPS assumption (30) sai** | Trung bình | Nếu FPS thật khác 30, tất cả window tính sai → cần kiểm tra metadata dataset gốc. Note rõ assumption trong báo cáo. |
| **Dataset là re-upload không chính thức** | Trung bình | Trích dẫn paper gốc, không claim đây là dataset chuẩn. Nếu có vấn đề license → thay nguồn chính thức từ cv.cs.nthu.edu.tw |
| **`utils/mar.py` và `utils/headpose.py` chưa có** | **Cao** | Script training cần import 2 file này. Nếu chưa implement → dùng stub `return 0.0` / `return (0.0, 0.0, 0.0)` và log warning. Khuyến nghị: hoàn thành trước khi chạy training. |
| **MediaPipe Face Landmarker không detect được mặt** | Thấp | Skip ảnh, log warning, không crash. Ước tính <5% ảnh bị skip (góc chụp xấu, che khuất) |
| **Imbalanced dataset** | Trung bình | Dùng `class_weight='balanced'` (RF) và `scale_pos_weight` (XGB). Báo cáo phân phối class trong training report. |
| **Overfitting với 40 features** | Trung bình | RF/XGB có cơ chế chống overfit (max_depth, ensemble). LOSO-CV 4 fold giúp phát hiện overfit (nếu 1 fold outlier). Feature importance chart giúp phát hiện feature noise. |
| **Dataset chỉ có 4 subject** | **Cao** | Kết quả LOSO-CV chỉ phản ánh khả năng tổng quát hoá trong 4 subject này. Không đại diện cho toàn bộ dân số. Xem limitation ở cuối file. Đề xuất mở rộng bằng dataset tự quay trong hướng phát triển. |

### Câu hỏi mở

Không có câu hỏi mở cần thêm vào `open-questions.md` — mọi quyết định đã được chốt.

## Ảnh hưởng tới service khác

**Không ảnh hưởng.** Pipeline training chạy độc lập, không đụng tới code runtime của bất kỳ service nào. Model output `model.pkl` sẽ được FEAT-rf-integration load sau.

`.opencode/knowledge/services-map.md` — **không cần cập nhật**.

## Hạn chế (Limitations)

⚠️ **Dataset chỉ có 4 subject** (`001, 002, 005, 006`). Kết quả LOSO-CV chỉ phản ánh khả năng tổng quát hoá của model trong phạm vi 4 subject này, không đảm bảo hiệu năng tương đương trên người dùng mới (subject chưa từng thấy). Đây là hạn chế cố hữu của NTHU-DDD bản Kaggle mirror — dataset gốc có nhiều subject hơn nhưng không có sẵn trên Kaggle.

**Hướng phát triển đề xuất**: Tự quay thêm dataset với nhiều subject hơn (≥ 10), đa dạng điều kiện ánh sáng/góc quay/kính đeo, để huấn luyện lại model có độ tổng quát hoá cao hơn.

## Trạng thái xác nhận

`[x] Đã xác nhận bởi người dùng ngày 2026-07-11`
