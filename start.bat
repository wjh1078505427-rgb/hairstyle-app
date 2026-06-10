@echo off
cd /d "%~dp0"

echo ============================================
echo   AI换发型 - 启动中...
echo ============================================

REM 启动 Cloudflare Tunnel（显示公网地址）
start "Cloudflare Tunnel" cmd /c "%~dp0..\..\..\cloudflared.exe tunnel --url http://localhost:8501 2>&1 | findstr /C:\"trycloudflare.com\" & pause"

REM 等待隧道建立
timeout /t 3 /nobreak >nul

REM 打开浏览器
start http://localhost:8501

REM 启动 Streamlit
streamlit run "%~dp0app.py" --server.port 8501
pause
