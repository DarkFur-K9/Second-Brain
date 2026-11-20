@echo off
title SecondSelf - Your Personal AI Second Brain
echo =================================================================
echo  🧠 Starting SecondSelf: Your Personal AI Second Brain
echo =================================================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found at .venv.
    echo [*] Please run: uv venv .venv ^&^& .venv\Scripts\activate ^&^& uv pip install -r requirements.txt
    pause
    exit /b 1
)

echo [*] Activating Python virtual environment...
call .venv\Scripts\activate.bat

echo [*] Launching Streamlit web application on http://localhost:8501...
streamlit run app.py

pause
