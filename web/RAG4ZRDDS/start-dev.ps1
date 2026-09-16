# RAG4ZRDDS 前端开发服务器启动脚本（PowerShell）
# 用法：在本目录执行  powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
# 提示：后端需先跑  make serve（127.0.0.1:8000）；后端换端口时先设 $env:RAG_BACKEND_URL。

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

Write-Host 'Checking node and npm availability...'
node --version
npm --version

if (-not (Test-Path 'node_modules')) {
    Write-Host 'node_modules 不存在，先执行 npm install ...'
    npm install
}

Write-Host ''
Write-Host 'Starting Vite dev server (Ctrl+C to stop)...'
npm run dev
