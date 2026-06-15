# Driver Service Specification

## Purpose

Driver Service là thành phần AI chịu trách nhiệm theo dõi trạng thái tài xế trong hệ thống ADAS.

Nhiệm vụ chính:

* Nhận video từ camera cabin
* Phân tích khuôn mặt tài xế
* Trích xuất các đặc trưng hành vi
* Đánh giá mức độ buồn ngủ
* Gửi cảnh báo

---

## Inputs

### Camera Cabin

Video Stream

FPS: 20-30

Resolution:

* 640x480
* 1280x720

---

## Outputs

Fatigue Status

* Awake
* Tired
* Drowsy
* Dangerous

---

## Features

### Eye Aspect Ratio (EAR)

Phát hiện mắt mở hoặc đóng.

### PERCLOS

Tỷ lệ thời gian mắt đóng.

### Mouth Aspect Ratio (MAR)

Phát hiện ngáp.

### Head Pose

Yaw

Pitch

Roll

---

## AI Model

Current:

Rule-Based

Future:

Random Forest

Input:

* EAR
* PERCLOS
* MAR
* Yaw
* Pitch
* Roll

Output:

* Awake
* Tired
* Drowsy
* Dangerous
