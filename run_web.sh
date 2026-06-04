#!/bin/bash
cd ~/BooklyTTS
source .venv/bin/activate 2>/dev/null || source venv/bin/activate 2>/dev/null
echo "🌐 BooklyTTS Web UI"
echo "   http://localhost:5000"
python3 -m flask --app app run --host=0.0.0.0 --port=5000 --no-debugger
