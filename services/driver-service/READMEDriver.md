# Driver Service - Driver Drowsiness Monitoring

## Overview

Driver Service là một microservice thuộc hệ thống Multimodal ADAS (Advanced Driver Assistance System).

Service này chịu trách nhiệm:

* Giám sát trạng thái tài xế theo thời gian thực
* Phát hiện buồn ngủ
* Phát hiện ngủ gật
* Phát hiện ngáp
* Phát hiện cúi đầu bất thường
* Cảnh báo nguy hiểm cho tài xế

---

## Current Scope

Hiện tại service tập trung vào:

* Face Landmark Detection
* Eye Aspect Ratio (EAR)
* PERCLOS
* Mouth Aspect Ratio (MAR)
* Head Pose Estimation
* Fatigue Analysis

---

## Technology Stack

### Computer Vision

* MediaPipe Face Landmarker
* OpenCV

### Machine Learning

* Random Forest
* Scikit-Learn

### Backend

* FastAPI

### Container

* Docker

---

## Detection Pipeline

Camera
↓
Face Landmarker
↓
Feature Extraction
↓
EAR
MAR
PERCLOS
Head Pose
↓
Fatigue Analysis
↓
Alert System

---

## Project Roadmap

### Phase 1

* Face Landmark Detection
* EAR Detection

### Phase 2

* MAR Detection
* PERCLOS Detection

### Phase 3

* Head Pose Estimation

### Phase 4

* Rule-Based Fatigue Detection

### Phase 5

* Random Forest Training

### Phase 6

* FastAPI Integration

### Phase 7

* Kafka Integration

---

## Setup

### Create Virtual Environment

```powershell
python -m venv .venv
```

### Activate

```powershell
.\.venv\Scripts\activate
```

### Install Dependencies

```powershell
pip install -r requirements.txt
```

### Run

```powershell
python main.py
```

---

## Required Assets

Download:

face_landmarker.task

Place it in:

driver-service/

---

## Current Status

Current Milestone:

* Face Landmarker Working
* Webcam Working
* Landmark Visualization Working

Next Milestone:

* EAR Detection
* Eye Closure Detection
