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
# TEST 2: Invalid file type
# ---------------------------------------------------------------------------
print("\n[2] POST /analyze-video — file type khong hop le (.txt)")
try:
    boundary = "----Boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
        f"hello\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    req = urllib.request.Request(
        f"{BASE_URL}/analyze-video",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        check("Reject invalid file", False, "Should have returned 400")
    except urllib.error.HTTPError as e:
        check("Reject invalid file (400)", e.code == 400, f"HTTP {e.code}")
except Exception as e:
    check("Reject invalid file", False, str(e))

# ---------------------------------------------------------------------------
# TEST 3: analyze-video with real MP4
# ---------------------------------------------------------------------------
print(f"\n[3] POST /analyze-video — {VIDEO_PATH}")
try:
    boundary = "----LaneBoundary7MA4"
    with open(VIDEO_PATH, "rb") as f:
        video_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="solidWhiteRight.mp4"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + video_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}/analyze-video",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=120)
    d = json.loads(r.read())

    check("Status 200", r.status == 200, f"HTTP {r.status}")
    check("status = ok", d.get("status") == "ok")
    check("frames_processed = 30", d.get("frames_processed") == 30,
          f"got {d.get('frames_processed')}")

    video_info = d.get("video", {})
    check("Video info present", bool(video_info),
          f"{video_info.get('width')}x{video_info.get('height')} "
          f"@ {video_info.get('fps')} fps, {video_info.get('duration_seconds')}s")

    lr = d.get("last_frame_result", {})
    check("last_frame_result present", bool(lr))
    check("num_detections >= 0", lr.get("num_detections", -1) >= 0,
          f"Detections: {lr.get('num_detections')}")
    check("YOLO running", "YOLO" in lr.get("message", ""),
          lr.get("message", "")[:80])

except FileNotFoundError:
    check("Video file exists", False, f"{VIDEO_PATH} not found")
except Exception as e:
    check("analyze-video", False, str(e))

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
