:: Start RAG4ZRDDS Web Dev Server
:: Run this script from an Administrator PowerShell to bypass execution policy restrictions

cd /d "%~dp0"

echo "Checking node and npm availability..."
node --version
npm --version

echo ""
echo "Starting Vite dev server... Press Ctrl+C to stop."
npm run dev
