"""
test_lane_service.py — Script test tất cả endpoints của lane-service
Chạy: py test_lane_service.py
"""
import json
import sys
import urllib.request
import urllib.error
import os

BASE_URL = "http://localhost:8002"
VIDEO_PATH = "data/test_videos/solidWhiteRight.mp4"
PASS = "PASS"
FAIL = "FAIL"
results = []


def check(name, ok, detail=""):
    icon = "[OK]" if ok else "[!!]"
    status = PASS if ok else FAIL
    print(f"  {icon} {name}: {status}")
    if detail:
        print(f"     {detail}")
    results.append(ok)


# ===========================================================================
print()
print("=" * 55)
print("  LANE-SERVICE TEST SUITE")
print("=" * 55)

# ---------------------------------------------------------------------------
# TEST 1: Health check
# ---------------------------------------------------------------------------
print("\n[1] GET /health")
try:
    r = urllib.request.urlopen(f"{BASE_URL}/health", timeout=5)
    d = json.loads(r.read())
    check("Status 200", r.status == 200, f"HTTP {r.status}")
    check("service = lane-service", d.get("service") == "lane-service", str(d))
except Exception as e:
    check("Health reachable", False, str(e))

# ---------------------------------------------------------------------------
# TEST 2: Detailed Health fields
# ---------------------------------------------------------------------------
print("\n[2] GET /health — Checking detailed status fields")
try:
    r = urllib.request.urlopen(f"{BASE_URL}/health", timeout=5)
    d = json.loads(r.read())
    check("rabbitmq status exists", "rabbitmq" in d, str(d))
    check("yolo_model status exists", "yolo_model" in d, str(d))
    check("deeplab_weights status exists", "deeplab_weights" in d, str(d))
    check("stream_source exists", "stream_source" in d, str(d))
except Exception as e:
    check("Health detailed fields", False, str(e))

# ---------------------------------------------------------------------------
# TEST 3: GET /stream availability
# ---------------------------------------------------------------------------
print("\n[3] GET /stream — Checking response header")
try:
    # Gửi request và chỉ kiểm tra headers, không đọc hết stream vì stream vô hạn
    req = urllib.request.Request(f"{BASE_URL}/stream")
    r = urllib.request.urlopen(req, timeout=5)
    check("Status 200", r.status == 200, f"HTTP {r.status}")
    content_type = r.getheader("Content-Type")
    check("Content-Type is multipart", "multipart/x-mixed-replace" in content_type, f"Content-Type: {content_type}")
except Exception as e:
    check("Stream reachable", False, str(e))

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
print("\n" + "="*55)
total = len(results)
passed = sum(results)
failed = total - passed
print(f"  Total: {total} test | [OK] {passed} pass | [!!] {failed} fail")
print("="*55 + "\n")
sys.exit(0 if failed == 0 else 1)
