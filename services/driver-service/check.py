import os, re

base = r"D:\multimodal-adas\services\driver-service\dataset\Multi class\train_cleaned"

pattern = re.compile(r"^(\d+)_(glasses|noglasses)_([a-zA-Z]+)_(\d+)_(drowsy|notdrowsy)\.jpg$")

subjects = set()
scenarios = set()
subject_scenario_pairs = set()

for root, dirs, files in os.walk(base):
    for f in files:
        m = pattern.match(f)
        if m:
            subject_id, glasses, scenario, frame_num, label = m.groups()
            subjects.add(subject_id)
            scenarios.add(scenario)
            subject_scenario_pairs.add((subject_id, scenario))

print(f"Số subject duy nhất: {len(subjects)} -> {sorted(subjects)}")
print(f"Số scenario duy nhất: {len(scenarios)} -> {sorted(scenarios)}")
print(f"Số cặp (subject, scenario) thực tế: {len(subject_scenario_pairs)}")