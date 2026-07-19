# FEAT-fatigue-classifier: Rule-Based Classifier + Pipeline Integration

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-drowsiness-detection.md` — AC-3.5 (Rule-based fallback), AC-4 (Output qua RabbitMQ)

## Service
**driver-service** — sửa `services/fatigue_detector.py`, `core/config.py`, `messaging/consumer.py`, `messaging/orchestrator.py`, `models/messages.py` (hoặc tạo mới)

## Mô tả chức năng

Tích hợp toàn bộ pipeline 3 tầng vào `FatigueDetector` và cập nhật output schema:

```
JPEG bytes → FaceLandmarkerService → FeatureService → RuleBasedClassifier → ResultPublisher
```

### Rule-Based Classifier (AC-3.5)

Implement `RuleBasedClassifier` với công thức PERCLOS-based 4 cấp:
- **Awake** (score 0-25): PERCLOS < 15% và không ngáp kéo dài
- **Tired** (score 26-50): PERCLOS 15-25%, hoặc ngáp lặp lại ≥ 3 lần/60s
- **Drowsy** (score 51-75): PERCLOS 25-40%, hoặc cúi/nghiêng đầu bất thường kéo dài ≥ 3s
- **Dangerous** (score 76-100): PERCLOS > 40%, hoặc microsleep (EAR < threshold ≥ 2s)

### Output Schema Update

Thay đổi message JSON publish lên `driver.result`:
```json
{
  "frame_id": 1234,
  "timestamp": 1712345678.123,
  "fatigue_score": 45,
  "fatigue_level": "Tired",
  "confidence": 0.85,
  "features": {
    "ear": 0.18,
    "perclos": 22.5,
    "mar": 0.15,
    "yaw": -5.2,
    "pitch": 3.1,
    "roll": 1.8
  },
  "classification_method": "rule_based"
}
```

## Acceptance Criteria

- [ ] **AC-F3.1**: `services/fatigue_detector.py` được refactor: nhận `FaceLandmarkerService` + `FeatureService` + `Classifier` qua constructor (DIP). Method `process(jpeg_bytes, frame_id, timestamp) -> FatigueResult`
- [ ] **AC-F3.2**: `services/rule_based_classifier.py` chứa `RuleBasedClassifier` implement đúng công thức 4 cấp từ AC-3.5. Method `classify(features: FeatureVector) -> ClassificationResult` trả về `(score, level, confidence)`
- [ ] **AC-F3.3**: Tất cả threshold (EAR, MAR, PERCLOS %, Pitch/Yaw góc độ, thời gian microsleep/ngáp) lưu trong `core/config.py` dưới dạng biến môi trường
- [ ] **AC-F3.4**: `ClassificationResult` là dataclass/Pydantic chứa: `fatigue_score: int`, `fatigue_level: str`, `confidence: float`, `classification_method: str`
- [ ] **AC-F3.5**: `messaging/consumer.py` (`FrameConsumer._on_frame_message`) cập nhật để gọi `FatigueDetector.process()` và publish kết quả đúng schema mới
- [ ] **AC-F3.6**: `models/messages.py` (hoặc file mới `models/fatigue.py`) chứa Pydantic model `FatigueResultMessage` khớp với JSON schema trên
- [ ] **AC-F3.7**: Khi không phát hiện mặt (`face_detected=False`) → `fatigue_level="Unknown"`, `fatigue_score=-1`, `confidence=0.0`, `features` toàn `0.0`
- [ ] **AC-F3.8**: `messaging/orchestrator.py` updated để wire: `FaceLandmarkerService` → `FeatureService` → `RuleBasedClassifier` → `FatigueDetector`
- [ ] **AC-F3.9**: `GET /stats` endpoint cập nhật trả về thêm `fatigue_level_distribution` (đếm số frame mỗi level)
- [ ] **AC-F3.10**: Pipeline hoàn chỉnh chạy được với rule-based classifier (chưa cần Random Forest), output đúng schema mới qua RabbitMQ

## Độ ưu tiên
**P0** — Đây là feature tích hợp chính, cho ra sản phẩm chạy được ngay với rule-based. Phụ thuộc FEAT-landmark-refactor + FEAT-feature-extraction.

## Phụ thuộc
- **FEAT-landmark-refactor**: Cần `FaceLandmarkerService`
- **FEAT-feature-extraction**: Cần `FeatureService` + `FeatureVector`
