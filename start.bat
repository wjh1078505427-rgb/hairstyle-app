@echo off
cd /d "%~dp0"
start http://localhost:8501
streamlit run "%~dp0app.py" --server.port 8501
pause
