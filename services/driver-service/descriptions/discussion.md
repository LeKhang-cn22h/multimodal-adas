# Technical Discussion

## Why MediaPipe?

Advantages:

* Fast
* Lightweight
* Real-time
* CPU Friendly
* No Training Required

Disadvantages:

* Sensitive to lighting
* Face occlusion issues

---

## Why Random Forest?

Advantages:

* Easy to train
* Small dataset requirement
* Fast inference
* Explainable

Disadvantages:

* Lower accuracy than Deep Learning

---

## Why Not CNN + LSTM?

Advantages:

* Higher accuracy
* Temporal modeling

Disadvantages:

* Requires GPU
* Large dataset
* Longer training time
* Higher deployment cost

---

## Decision

Current project adopts:

MediaPipe
+
Feature Engineering
+
Random Forest

Reason:

Best trade-off between:

* Accuracy
* Development time
* Hardware cost
* Real-time performance
