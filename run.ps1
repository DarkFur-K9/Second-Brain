# SecondSelf: Streamlit Launch Script for PowerShell
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " 🧠 Starting SecondSelf: Your Personal AI Second Brain" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host ""

$venvPython = ".\.venv\Scripts\python.exe"
$venvStreamlit = ".\.venv\Scripts\streamlit.exe"

if (-not (Test-Path $venvStreamlit)) {
    Write-Host "[!] Streamlit binary not found in .venv." -ForegroundColor Red
    Write-Host "[*] Please initialize the environment: uv venv .venv; .\.venv\Scripts\activate; uv pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

Write-Host "[*] Launching Streamlit web application on http://localhost:8501..." -ForegroundColor Green
& $venvStreamlit run app.py
