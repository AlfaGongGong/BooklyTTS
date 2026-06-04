#!/bin/bash
PID_FILE="$HOME/.booklytts_sync.pid"

case "$1" in
    start)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "✅ Sync već aktivan (PID: $(cat $PID_FILE))"
        else
            echo "🚀 Pokrećem mirror sync..."
            nohup bash "$HOME/BooklyTTS/sync_mirror.sh" > "$HOME/.booklytts_sync.log" 2>&1 &
            echo $! > "$PID_FILE"
            echo "✅ Sync pokrenut (PID: $!)"
        fi
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            kill $(cat "$PID_FILE") 2>/dev/null
            rm "$PID_FILE"
            echo "🛑 Sync zaustavljen"
        else
            echo "❌ Sync nije aktivan"
        fi
        ;;
    status)
        if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
            echo "✅ Sync aktivan (PID: $(cat $PID_FILE))"
        else
            echo "❌ Sync nije aktivan"
        fi
        ;;
    log)
        tail -f "$HOME/.booklytts_sync.log"
        ;;
    *)
        echo "Koristenje: $0 {start|stop|status|log}"
        ;;
esac
