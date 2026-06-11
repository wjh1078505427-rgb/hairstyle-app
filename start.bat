@echo off
cd /d "%~dp0"

echo ============================================
echo   AI换发型 - 启动中...
echo ============================================

REM 启动 Serveo 永久隧道（地址: https://ai-hairstyle.serveo.net）
start "Serveo Tunnel" cmd /c "ssh -o StrictHostKeyChecking=no -R ai-hairstyle:80:localhost:8501 serveo.net"

REM 等待隧道建立
timeout /t 3 /nobreak >nul

REM 打开浏览器
start http://localhost:8501

REM 启动 Streamlit
streamlit run "%~dp0app.py" --server.port 8501
pause
