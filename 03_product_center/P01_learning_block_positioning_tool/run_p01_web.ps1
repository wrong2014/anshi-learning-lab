$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\10707\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Server = Join-Path $ScriptDir "web_app\server.py"

Write-Host "Starting P01 backend API..."
Write-Host "API: http://127.0.0.1:8765"
Write-Host "Start frontend in another terminal:"
Write-Host "  cd $ScriptDir\web_app\frontend"
Write-Host "  npm run dev"
Write-Host "Open app: http://localhost:5173/"
& $Python $Server
