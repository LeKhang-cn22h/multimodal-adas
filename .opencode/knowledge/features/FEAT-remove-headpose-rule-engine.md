# FEAT-remove-headpose-rule-engine: Refactor DrowsinessRuleEngine interface & logic

## Thuộc Requirement
`.opencode/knowledge/requirements/REQ-remove-headpose.md`

## Service
`driver-service` — file `app/services/decision/drowsiness_rule_engine.py`

## Mô tả chức năng
Thay đổi interface `DrowsinessRuleEngine.decide()` để nhận thêm tham số `crop_valid`, đơn giản hóa logic quyết định trạng thái, chỉ trả về 4 trạng thái mới:

```
decide(
    face_detected: bool,
    crop_valid: bool,
    eye_buffer_result: dict | None,
    mouth_buffer_result: dict | None,
) -> DrowsinessLevel
```

Logic:
1. `not face_detected` → `NO_FACE`
2. `not crop_valid` → `FACE_DETECTED_BUT_INVALID`
3. `is_microsleep` → `DROWSY`
4. `is_perclos_drowsy` → `DROWSY`
5. `is_real_yawn` → `DROWSY`
6. Otherwise → `NORMAL`

Gộp tất cả trường hợp buồn ngủ (microsleep, perclos, real_yawn) thành 1 trạng thái duy nhất: `DROWSY`.

## Acceptance Criteria
- AC1: `decide()` nhận 4 tham số đúng signature trên.
- AC2: Trả về `NO_FACE` khi `face_detected=False`.
- AC3: Trả về `FACE_DETECTED_BUT_INVALID` khi `face_detected=True, crop_valid=False`.
- AC4: Trả về `DROWSY` khi có microsleep, perclos, hoặc real_yawn.
- AC5: Trả về `NORMAL` trong mọi trường hợp còn lại.
- AC6: Không còn return `DROWSY_MILD`, `DROWSY_SEVERE`, `LOOKING_AWAY`, `YAWNING`.

## Độ ưu tiên
**P0** — Rule engine là trung tâm quyết định trạng thái.

## Phụ thuộc
- `FEAT-remove-headpose-drowsiness-level` (cần enum mới `DROWSY`, `FACE_DETECTED_BUT_INVALID`).
