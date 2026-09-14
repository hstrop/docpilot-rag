$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = (Get-Command python -ErrorAction Stop).Source }
$env:PYTHONPATH = Join-Path $root "src"
$env:DOCPILOT_MODE = "demo"
$env:DOCPILOT_VECTOR_BACKEND = "memory"
$env:DOCPILOT_AI_BACKEND = "deterministic"
Write-Host "DocPilot Web: http://127.0.0.1:8000/"
Write-Host "按 Ctrl+C 停止服务。"
& $python -m uvicorn docpilot.api:app --host 127.0.0.1 --port 8000
