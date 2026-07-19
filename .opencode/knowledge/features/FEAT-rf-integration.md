# FEAT-rf-integration: Tích hợp Random Forest vào Pipeline

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-drowsiness-detection.md` — AC-3.1, AC-3.2, AC-3.3 (load model), AC-3.5 (fallback)

## Service
**driver-service** — sửa `services/fatigue_detector.py`, `messaging/orchestrator.py`, `core/config.py`

## Mô tả chức năng

Tích hợp model Random Forest đã train (từ FEAT-dataset-training) vào pipeline phân loại fatigue. Khi model `.joblib` tồn tại → dùng RF để classify; khi không tồn tại hoặc lỗi → tự động fallback về `RuleBasedClassifier`.

### Cơ chế chọn classifier

```
if model_path tồn tại và load thành công:
    classifier = RFClassifier(model_path)
    classification_method = "random_forest"
else:
    classifier = RuleBasedClassifier()
    classification_method = "rule_based"
```

Cả 2 classifier implement cùng interface `IClassifier` với method `classify(features: FeatureVector) -> ClassificationResult`.

### Load model trong lifespan

- `MessagingOrchestrator.start()` → thử load `fatigue_rf_model.joblib`
- Nếu load thành công → `classifier = RFClassifier`
- Nếu lỗi (file không tồn tại, version mismatch...) → log warning + `classifier = RuleBasedClassifier`
- KHÔNG crash app nếu model lỗi

## Acceptance Criteria

- [ ] **AC-F5.1**: `services/classifier_interface.py` chứa abstract base class `IClassifier` với method `classify(features: FeatureVector) -> ClassificationResult`
- [ ] **AC-F5.2**: `services/rule_based_classifier.py` implement `IClassifier` (refactor từ FEAT-fatigue-classifier nếu cần)
- [ ] **AC-F5.3**: `services/rf_classifier.py` chứa `RFClassifier` implement `IClassifier`, load model `.joblib` trong constructor, method `classify()` gọi `model.predict_proba()` → chọn class có probability cao nhất → map về score + level
- [ ] **AC-F5.4**: `RFClassifier` map 4-class output (0-1-2-3) về Fatigue Score: class 0 → score 12, class 1 → score 38, class 2 → score 63, class 3 → score 88 (midpoint của mỗi range). Confidence = `max(proba)`
- [ ] **AC-F5.5**: `core/config.py` thêm biến `RF_MODEL_PATH` (default: `training/output/fatigue_rf_model.joblib`), `RF_FALLBACK_ENABLED` (default: `True`)
- [ ] **AC-F5.6**: `messaging/orchestrator.py` thử load model RF trong `start()`, fallback về rule-based nếu lỗi, inject classifier vào `FatigueDetector`
- [ ] **AC-F5.7**: `FatigueDetector.process()` sử dụng classifier được inject, không cần biết đang dùng RF hay rule-based
- [ ] **AC-F5.8**: Kết quả publish lên RabbitMQ có field `classification_method: "random_forest" | "rule_based"` để consumer biết nguồn gốc kết quả
- [ ] **AC-F5.9**: `GET /stats` endpoint cập nhật thêm `classification_method` hiện tại
- [ ] **AC-F5.10**: App khởi động thành công kể cả khi model `.joblib` không tồn tại (chỉ log warning, không crash)

## Độ ưu tiên
**P0** — Đây là feature cuối cùng hoàn thiện pipeline, cho phép chuyển từ rule-based sang ML-based. Phụ thuộc FEAT-fatigue-classifier + FEAT-dataset-training.

## Phụ thuộc
- **FEAT-fatigue-classifier**: Cần pipeline đã chạy được với rule-based, `ClassificationResult` schema đã định nghĩa
- **FEAT-dataset-training**: Cần file `fatigue_rf_model.joblib` đã train
