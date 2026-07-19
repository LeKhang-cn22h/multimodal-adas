@echo off
:: start_all.bat - Script khởi chạy các service và WebView trên Windows Command Prompt / Nhấp đúp chuột

echo =================================================================
echo    KHIEN CHAY HE THONG ADAS (DRIVER ^& LANE SERVICES)
echo =================================================================

:: 1. Kiem tra moi truong ao
if not exist ".venv" (
    echo [!] Khong tim thay thu muc moi truong ao .venv o thu muc goc.
    echo     Vui long cai dat moi truong truoc.
    pause
    exit /b 1
)

set PYTHON_ENV=.venv\Scripts\python.exe

:: 2. Khoi chay driver-service (Port 8001) duoi nen
echo [*] Dang khoi dong driver-service (Port 8001)...
start /B "" %PYTHON_ENV% services\driver-service\main.py > driver_service_bat.log 2>&1

:: 3. Khoi chay lane-service (Port 8002) duoi nen
echo [*] Dang khoi dong lane-service (Port 8002)...
start /B "" %PYTHON_ENV% services\lane-service\app\main.py > lane_service_bat.log 2>&1

echo [*] Logs duoc ghi nhan tai driver_service_bat.log va lane_service_bat.log
echo -----------------------------------------------------------------
echo [*] Cho 6 giay de he thong tai mo hinh AI ^& khoi dong Uvicorn...
timeout /t 6 /nobreak

:: 4. Mo trinh duyet voi file webview.html
if exist "webview.html" (
    echo [*] Dang mo trinh duyet voi giao dien WebView...
    start webview.html
) else (
    echo [!] Khong tim thay file webview.html tai thu muc goc.
)

echo =================================================================
echo    HE THONG DA SAN SANG!
echo    De tat cac dich vu, hay chay script: stop_all.bat
echo =================================================================
