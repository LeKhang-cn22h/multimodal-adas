/* =========================================================
   app.js - MULTIMODAL-ADAS Dashboard
   Kết nối với FastAPI backend:
     GET  /health          - kiểm tra server
     GET  /stream          - MJPEG live stream
     GET  /videos          - danh sách video đã lưu
     POST /analyze-video   - phân tích video và trả kết quả
     POST /set-stream      - đổi video đang phát
   ========================================================= */

const API = "";   // same origin

// ── DOM refs ──────────────────────────────────────────────
const srvBadge      = document.getElementById("srv-status");
const videoSelect   = document.getElementById("video-select");
const camStatus     = document.getElementById("cam-status");
const streamImg     = document.getElementById("stream-img");
const fileInput     = document.getElementById("file-input");
const dropArea      = document.getElementById("drop-area");
const fileNameEl    = document.getElementById("file-name");
const analyzeBtn    = document.getElementById("analyze-btn");
const progressWrap  = document.getElementById("progress-bar-wrap");
const progressBar   = document.getElementById("progress-bar");
const analyzeStatus = document.getElementById("analyze-status");
const kvDirection   = document.getElementById("kv-direction");
const kvOffset      = document.getElementById("kv-offset");
const kvTargets     = document.getElementById("kv-targets");
const kvFrames      = document.getElementById("kv-frames");
const kvResolution  = document.getElementById("kv-resolution");
const kvFps         = document.getElementById("kv-fps");
const jsonOutput    = document.getElementById("json-output");
const jsonPanel     = document.getElementById("json-panel");
const jsonChev      = document.getElementById("json-chev");
const historyList   = document.getElementById("history-list");
const alertList     = document.getElementById("alert-list");

let selectedFile = null;
let analyzeHistory = [];

// ── Health Check ──────────────────────────────────────────
async function checkHealth() {
    try {
        const res = await fetch(`${API}/health`);
        if (res.ok) {
            srvBadge.textContent = "● Server OK";
            srvBadge.className = "srv-badge srv-ok";
        } else {
            throw new Error("not ok");
        }
    } catch {
        srvBadge.textContent = "● Offline";
        srvBadge.className = "srv-badge srv-error";
    }
}
checkHealth();
setInterval(checkHealth, 15000);

// ── Load video list from /videos endpoint ─────────────────
async function loadVideoList() {
    try {
        const res = await fetch(`${API}/videos`);
        if (!res.ok) throw new Error();
        const data = await res.json();
        const files = data.videos || [];
        videoSelect.innerHTML = "";
        if (files.length === 0) {
            const opt = document.createElement("option");
            opt.value = "solidWhiteRight.mp4";
            opt.textContent = "solidWhiteRight.mp4";
            videoSelect.appendChild(opt);
        } else {
            files.forEach(f => {
                const opt = document.createElement("option");
                opt.value = f;
                opt.textContent = f;
                videoSelect.appendChild(opt);
            });
        }
        camStatus.textContent = `Dang phat: ${videoSelect.value}`;
    } catch {
        camStatus.textContent = "Khong the tai danh sach video";
    }
}
loadVideoList();

// ── Switch active stream video ────────────────────────────
async function switchVideo(filename) {
    if (!filename) return;
    try {
        await fetch(`${API}/set-stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename })
        });
        camStatus.textContent = `Dang phat: ${filename}`;
        // Force stream reload
        streamImg.src = `/stream?t=${Date.now()}`;
    } catch {
        camStatus.textContent = "Loi khi doi nguon video";
    }
}

// ── File selection ─────────────────────────────────────────
function onFileSelected(input) {
    const file = input.files[0];
    if (!file) return;
    selectedFile = file;
    fileNameEl.textContent = file.name;
    analyzeBtn.disabled = false;
    analyzeStatus.textContent = "";
}

function handleDrop(e) {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    selectedFile = file;
    fileNameEl.textContent = file.name;
    analyzeBtn.disabled = false;
    analyzeStatus.textContent = "";
}

// ── Analyze video ─────────────────────────────────────────
async function analyzeVideo() {
    if (!selectedFile) return;

    analyzeBtn.disabled = true;
    progressWrap.classList.remove("hidden");
    progressBar.style.width = "0%";
    analyzeStatus.textContent = "Dang tai video len server...";

    // Simulate progress (real progress via XHR below)
    let fakeProgress = 0;
    const fakeTick = setInterval(() => {
        fakeProgress = Math.min(fakeProgress + 3, 85);
        progressBar.style.width = fakeProgress + "%";
    }, 200);

    try {
        const formData = new FormData();
        formData.append("file", selectedFile);

        analyzeStatus.textContent = "Dang xu ly ADAS pipeline...";
        const res = await fetch(`${API}/analyze-video`, {
            method: "POST",
            body: formData,
        });

        clearInterval(fakeTick);
        progressBar.style.width = "100%";

        if (!res.ok) {
            const err = await res.json();
            analyzeStatus.textContent = `Loi: ${err.detail || res.status}`;
            addAlert(`Loi phan tich: ${selectedFile.name}`, "urgent");
            return;
        }

        const data = await res.json();
        analyzeStatus.textContent = `Hoan thanh - ${data.frames_processed} frames`;

        updateADASPanel(data);
        addHistory(data);

        // Switch stream to the just-analyzed file
        const filename = selectedFile.name;
        await fetch(`${API}/set-stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename })
        }).catch(() => {});
        streamImg.src = `/stream?t=${Date.now()}`;
        camStatus.textContent = `Dang phat: ${filename}`;

        // Refresh video dropdown
        await loadVideoList();

    } catch (err) {
        clearInterval(fakeTick);
        analyzeStatus.textContent = `Loi ket noi: ${err.message}`;
        addAlert("Loi ket noi server", "urgent");
    } finally {
        analyzeBtn.disabled = false;
        setTimeout(() => {
            progressWrap.classList.add("hidden");
            progressBar.style.width = "0%";
        }, 1500);
    }
}

// ── Update ADAS KV panel ──────────────────────────────────
function updateADASPanel(data) {
    const last = data.last_frame_result || data; // Ho tro ca ket qua analyze va live-status
    const direction  = last.direction || "UNKNOWN";
    const offset     = last.lane_offset;
    const numDets    = last.num_detections || 0;
    const frames     = data.frames_processed || "--";
    const videoInfo  = data.video || {};
    const width      = videoInfo.width || "--";
    const height     = videoInfo.height || "--";
    const fps        = videoInfo.fps || "--";

    // Direction badge
    let dirBadge, dirClass;
    if (["LEFT", "RIGHT"].includes(direction)) {
        dirBadge = `Chech lan (${direction})`; dirClass = "urgent";
        addAlert(`Canh bao: Chech lan ${direction}`, "urgent");
    } else if (direction === "UNKNOWN") {
        dirBadge = "Chua nhan dien"; dirClass = "neutral";
    } else {
        dirBadge = `An toan (${direction})`; dirClass = "safe";
    }
    kvDirection.innerHTML = `<span class="badge ${dirClass}">${dirBadge}</span>`;

    // Offset
    let offVal = offset !== null && offset !== undefined ? `${offset} m` : "--";
    let offClass = "safe";
    if (offset !== null && offset !== undefined && Math.abs(offset) > 0.5) offClass = "pending";
    kvOffset.innerHTML = `<span class="badge ${offClass}">${offVal}</span>`;

    // Targets
    let targClass = numDets > 0 ? "info" : "neutral";
    let targText  = numDets > 0 ? `${numDets} phuong tien` : "Khong phat hien";
    kvTargets.innerHTML = `<span class="badge ${targClass}">${targText}</span>`;

    kvFrames.textContent    = frames;
    if (width !== "--" || kvResolution.textContent === "--") {
        kvResolution.textContent = `${width}x${height}`;
    }
    if (fps !== "--" || kvFps.textContent === "--") {
        kvFps.textContent        = fps;
    }

    // Render danh sach xe tu gRPC vehicle-service
    const vehicleListPanel = document.getElementById("vehicle-list-panel");
    if (vehicleListPanel) {
        const objects = last.objects || [];
        if (!configState.vehicle_detection) {
            vehicleListPanel.innerHTML = `<div class="see-more" style="color:var(--text-dim);">Chuc nang nhan dien xe da tat</div>`;
        } else if (objects.length === 0) {
            vehicleListPanel.innerHTML = `<div class="see-more">Khong phat hien phuong tien</div>`;
        } else {
            vehicleListPanel.innerHTML = objects.map(obj => {
                let badgeClass = "safe";
                let badgeText = "An toan";
                if (obj.color === "orange") {
                    badgeClass = "warning";
                    badgeText = "Canh bao";
                } else if (obj.color === "red") {
                    badgeClass = "danger";
                    badgeText = "Nguy hiem";
                }
                
                return `
                    <div class="vehicle-item">
                        <div>
                            <span class="v-id">#${obj.track_id}</span>
                            <span class="v-class">${obj.class_name}</span>
                        </div>
                        <div>
                            <span class="v-dist">${obj.distance} m</span>
                            <span class="v-badge ${badgeClass}">${badgeText}</span>
                        </div>
                    </div>
                `;
            }).join("");
        }
    }

    // JSON output
    jsonOutput.textContent = JSON.stringify(data, null, 2);
}

// ── Toggle JSON panel ─────────────────────────────────────
function toggleJsonPanel() {
    jsonPanel.classList.toggle("hidden");
    jsonChev.textContent = jsonPanel.classList.contains("hidden") ? "▶" : "▼";
}

// ── Toggle sidebar panels ─────────────────────────────────
function togglePanel(header) {
    const body = header.nextElementSibling;
    if (!body) return;
    body.style.display = (body.style.display === "none") ? "" : "none";
}

// ── History ───────────────────────────────────────────────
function addHistory(data) {
    const filename   = data.filename || "video";
    const frames     = data.frames_processed;
    const direction  = (data.last_frame_result || {}).direction || "UNKNOWN";
    const badgeClass = ["LEFT","RIGHT"].includes(direction) ? "urgent" : direction === "UNKNOWN" ? "neutral" : "safe";

    analyzeHistory.unshift({ filename, frames, direction, badgeClass });
    if (analyzeHistory.length > 10) analyzeHistory.pop();

    historyList.innerHTML = analyzeHistory.map(h => `
        <div class="hist-item">
            <span class="hname">${h.filename}</span>
            <span class="badge ${h.badgeClass}">${h.direction}</span>
        </div>
    `).join("");
}

// ── Alert list ────────────────────────────────────────────
function addAlert(msg, type = "neutral") {
    const existing = alertList.querySelector(".see-more, .alert-item.neutral[data-placeholder]");
    if (existing && existing.dataset.placeholder) existing.remove();

    const div = document.createElement("div");
    div.className = `alert-item ${type}`;
    div.textContent = `● ${msg}`;
    alertList.prepend(div);

    if (alertList.children.length > 8) {
        alertList.removeChild(alertList.lastChild);
    }
}

// ── Bo loc tai nguyen (Toggle API Toggles) ──────────────────
let configState = {
    lane_detection: true,
    deeplab_segmentation: true,
    vehicle_detection: true,
    driver_monitoring: true,
    seatbelt_detection: true
};

async function syncToggles() {
    try {
        const res = await fetch(`${API}/api/config`);
        if (!res.ok) return;
        configState = await res.json();
        
        updateToggleUI("lane", configState.lane_detection);
        updateToggleUI("vehicle", configState.vehicle_detection);
        updateToggleUI("deeplab", configState.deeplab_segmentation);
        updateToggleUI("driver", configState.driver_monitoring);
        updateToggleUI("seatbelt", configState.seatbelt_detection);
    } catch (e) {
        console.error("Loi dong bo bo loc", e);
    }
}

function updateToggleUI(service, isActive) {
    const el = document.getElementById(`toggle-${service}`);
    if (!el) return;
    if (isActive) {
        el.classList.remove("off");
    } else {
        el.classList.add("off");
    }
}

async function onToggleClick(service, toggleId) {
    const element = document.getElementById(toggleId);
    if (!element) return;

    element.classList.toggle("off");
    const isActive = !element.classList.contains("off");
    
    if (service === "camera") {
        addAlert(`Camera ADAS: ${isActive ? 'BAT' : 'TAT'}`);
        return;
    }
    
    if (service === "lane") configState.lane_detection = isActive;
    else if (service === "vehicle") configState.vehicle_detection = isActive;
    else if (service === "deeplab") configState.deeplab_segmentation = isActive;
    else if (service === "driver") configState.driver_monitoring = isActive;
    else if (service === "seatbelt") configState.seatbelt_detection = isActive;
    
    try {
        const res = await fetch(`${API}/api/config`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(configState)
        });
        if (res.ok) {
            addAlert(`Bo loc ${service.toUpperCase()}: ${isActive ? 'BAT' : 'TAT'}`);
        } else {
            throw new Error();
        }
    } catch (e) {
        addAlert("Khong the cap nhat bo loc len server", "urgent");
        // Revert UI on failure
        element.classList.toggle("off");
    }
}

// ── Polling Live Stats ────────────────────────────────────
async function pollLiveStats() {
    // Chi poll neu stream-img dang duoc load (nguoi dung dang xem live stream)
    if (streamImg.src && !streamImg.src.includes("placeholder")) {
        try {
            const res = await fetch(`${API}/api/live-status`);
            if (res.ok) {
                const data = await res.json();
                if (data && Object.keys(data).length > 0) {
                    updateADASPanel(data);
                }
            }
        } catch (e) {
            // silent catch
        }
    }
}

// ── Polling Aggregator Alerts ─────────────────────────────
async function pollAggregatorEvents() {
    try {
        const res = await fetch(`${API}/api/events?limit=20`);
        if (!res.ok) return;
        const events = await res.json();
        
        // Filter events based on active services
        const filtered = events.filter(e => {
            if (e.source === "driver-service" && !configState.driver_monitoring) return false;
            if (e.source === "seatbelt-service" && !configState.seatbelt_detection) return false;
            if (e.source === "lane-service" && !configState.lane_detection) return false;
            if (e.source === "vehicle-service" && !configState.vehicle_detection) return false;
            return true;
        });
        
        if (filtered.length > 0) {
            alertList.innerHTML = filtered.map(e => {
                let badgeClass = "neutral";
                if (e.alert_level === "DANGEROUS" || e.alert_level === "DROWSY" || e.alert_level === "WARNING") {
                    badgeClass = "urgent";
                } else if (e.alert_level === "TIRED") {
                    badgeClass = "pending";
                }
                
                let msg = e.data?.message || `Event from ${e.source}`;
                return `<div class="alert-item ${badgeClass}">● ${msg}</div>`;
            }).join("");
        } else {
            alertList.innerHTML = `<div class="alert-item neutral">Chua co canh bao</div>`;
        }
    } catch (e) {
        // silent catch
    }
}

// Khoi dong cac tien trinh khi load trang
syncToggles();
setInterval(pollLiveStats, 500);
setInterval(pollAggregatorEvents, 1500);
