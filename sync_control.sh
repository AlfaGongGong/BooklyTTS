#!/bin/bash
# Kontrola sync servisa za BooklyTTS

LOG_FILE="$HOME/booklytts_sync.log"

case "$1" in
    start)
        echo "🚀 Pokrecem sync..."
        cd ~/BooklyTTS
        source .venv/bin/activate
        nohup python3 sync_bidirectional.py > "$LOG_FILE" 2>&1 &
        echo "PID: $!"
        echo "Log: $LOG_FILE"
        ;;
    stop)
        echo "🛑 Zaustavljam sync..."
        pkill -f sync_bidirectional.py 2>/dev/null
        echo "Zaustavljeno"
        ;;
    status)
        if pgrep -f sync_bidirectional.py > /dev/null; then
            echo "✅ Sync aktivan (PID: $(pgrep -f sync_bidirectional.py))"
        else
            echo "❌ Sync nije aktivan"
        fi
        ;;
    log)
        tail -f "$LOG_FILE"
        ;;
    *)
        echo "Koristenje: $0 {start|stop|status|log}"
        ;;
esac
