$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = "C:\Users\10707\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$Server = Join-Path $ScriptDir "web_app\server.py"

Write-Host "Starting P01 web prototype..."
Write-Host "Open: http://127.0.0.1:8765"
& $Python $Server
