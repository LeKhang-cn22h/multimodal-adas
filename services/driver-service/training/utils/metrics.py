"""Tính toán các metric đánh giá — dùng chung cho eye và mouth,
cho cả lúc train (theo dõi từng epoch) và evaluate.py (đánh giá cuối)."""

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> dict:
    auc = roc_auc_score(y_true, y_proba) if len(set(y_true)) > 1 else 0.5
    return {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "auc": auc,
    }


def get_classification_report(y_true: np.ndarray, y_pred: np.ndarray, class_names: list[str]) -> str:
    return classification_report(y_true, y_pred, target_names=class_names, zero_division=0)


def get_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    return confusion_matrix(y_true, y_pred)