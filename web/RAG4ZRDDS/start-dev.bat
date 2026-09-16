@echo off
echo Starting RAG4ZRDDS Web Dev Server...
cd /d "%~dp0"
set NODE_OPTIONS=--max-old-space-size=4096
call npm run dev