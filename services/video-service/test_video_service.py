"""
test_video_service.py — Script test các endpoints của video-service
Chạy: py test_video_service.py
"""
import json
import os
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8006"
TEST_VIDEO_SRC = "../lane-service/data/test_videos/solidWhiteRight.mp4"
FILENAME = "test_video.mp4"

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


# Đảm bảo video nguồn tồn tại trước khi chạy test upload
if not os.path.exists(TEST_VIDEO_SRC):
    # Thử tìm tương đối từ app/ hoặc workspace
    alternative_path = "services/lane-service/data/test_videos/solidWhiteRight.mp4"
    if os.path.exists(alternative_path):
        TEST_VIDEO_SRC = alternative_path
    else:
        print(f"LỖI: Không tìm thấy file video nguồn để test tại {TEST_VIDEO_SRC}")
        sys.exit(1)

print()
print("=" * 55)
print("  VIDEO-SERVICE TEST SUITE")
print("=" * 55)

# ---------------------------------------------------------------------------
# TEST 1: Health check
# ---------------------------------------------------------------------------
print("\n[1] GET /health")
try:
    r = urllib.request.urlopen(f"{BASE_URL}/health", timeout=5)
    d = json.loads(r.read())
    check("Status 200", r.status == 200, f"HTTP {r.status}")
    check("service = video-service", d.get("service") == "video-service", str(d))
except Exception as e:
    check("Health reachable", False, str(e))

# ---------------------------------------------------------------------------
# TEST 2: POST /upload
# ---------------------------------------------------------------------------
print("\n[2] POST /upload")
try:
    boundary = "----VideoBoundaryXYZ"
    with open(TEST_VIDEO_SRC, "rb") as f:
        video_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{FILENAME}"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + video_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        f"{BASE_URL}/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    r = urllib.request.urlopen(req, timeout=10)
    d = json.loads(r.read())

    check("Upload Status 200", r.status == 200, f"HTTP {r.status}")
    check("status = success", d.get("status") == "success")
    check("filename match", d.get("filename") == FILENAME, str(d))
    check("stream_url present", "stream_url" in d, str(d))
except Exception as e:
    check("Upload failed", False, str(e))

# ---------------------------------------------------------------------------
# TEST 3: GET /videos (List)
# ---------------------------------------------------------------------------
print("\n[3] GET /videos")
try:
    r = urllib.request.urlopen(f"{BASE_URL}/videos", timeout=5)
    d = json.loads(r.read())
    check("List Status 200", r.status == 200, f"HTTP {r.status}")
    check("total_count > 0", d.get("total_count", 0) > 0, str(d))
    
    # Tìm kiếm file đã upload trong danh sách
    found = any(v.get("filename") == FILENAME for v in d.get("videos", []))
    check("Uploaded video in list", found)
except Exception as e:
    check("List failed", False, str(e))

# ---------------------------------------------------------------------------
# TEST 4: GET /videos/{filename} (Download)
# ---------------------------------------------------------------------------
print(f"\n[4] GET /videos/{FILENAME}")
try:
    r = urllib.request.urlopen(f"{BASE_URL}/videos/{FILENAME}", timeout=5)
    check("Download Status 200", r.status == 200, f"HTTP {r.status}")
    check("Content-Type is video/mp4", r.headers.get("Content-Type") == "video/mp4")
    # Đọc thử một vài byte đầu xem có đúng không
    data = r.read(100)
    check("Data readable", len(data) > 0)
except Exception as e:
    check("Download failed", False, str(e))

# ---------------------------------------------------------------------------
# TEST 5: GET /videos/{filename}/stream (Frame Streaming)
# ---------------------------------------------------------------------------
print(f"\n[5] GET /videos/{FILENAME}/stream")
try:
    r = urllib.request.urlopen(f"{BASE_URL}/videos/{FILENAME}/stream", timeout=5)
    check("Stream Status 200", r.status == 200, f"HTTP {r.status}")
    check("Content-Type is multipart/x-mixed-replace", 
          "multipart/x-mixed-replace" in r.headers.get("Content-Type", ""))
    
    # Đọc thử một phần nhỏ dữ liệu của stream (MJPEG frame boundary)
    chunk = r.read(500)
    check("Stream chunk readable", b"--frame" in chunk or len(chunk) > 0)
except Exception as e:
    check("Streaming failed", False, str(e))

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
