import joblib
model = joblib.load("training/output/model.pkl")
print("classes_:", model.classes_)
print("dtype:", model.classes_.dtype)
print("drowsy_idx:", list(model.classes_).index(1))