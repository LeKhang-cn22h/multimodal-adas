@echo off
:: stop_all.bat - Script dừng nhanh các service ADAS đang chiếm dụng cổng 8001 và 8002 trên Windows

echo =================================================================
echo    DANG DUNG CAC DICH VU ADAS...
echo =================================================================

:: Giai phong cong 8001 (driver-service)
echo [*] Kiem tra cong 8001...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8001 ^| findstr LISTENING') do (
    echo [✓] Dang tat tien trinh %%a dang chay tren cong 8001...
    taskkill /F /PID %%a
)

:: Giai phong cong 8002 (lane-service)
echo [*] Kiem tra cong 8002...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8002 ^| findstr LISTENING') do (
    echo [✓] Dang tat tien trinh %%a dang chay tren cong 8002...
    taskkill /F /PID %%a
)

echo -----------------------------------------------------------------
echo [✓] Hoan thanh don dep cac dich vu ADAS!
echo =================================================================
pause
