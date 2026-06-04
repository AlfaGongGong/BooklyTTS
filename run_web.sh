#!/bin/bash
source .venv/bin/activate
export FLASK_APP=app
echo "🌐 BooklyTTS Web UI"
echo "   http://localhost:5000"
python3 -m flask run --host=0.0.0.0 --port=5000
