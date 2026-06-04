#!/bin/bash
# BooklyTTS Mirror Sync - Folderi uvijek identični
# Pokreni: bash sync_mirror.sh

TERMUX_DIR="$HOME/BooklyTTS"
SDCARD_DIR="/sdcard/termux/BooklyTTS"

EXCLUDE=".venv|.git|__pycache__|.gitkeep|*.pyc"

echo "========================================"
echo "  BooklyTTS Mirror Sync"
echo "  📱 $TERMUX_DIR"
echo "  💾 $SDCARD_DIR"
echo "  ↕️  Dvosmjerni sync u realnom vremenu"
echo "========================================"
echo ""

# Inicijalni sync u oba smjera
echo "🔄 Inicijalni sync..."
rsync -av --exclude='.venv' --exclude='.git' --exclude='__pycache__' "$TERMUX_DIR"/ "$SDCARD_DIR"/
rsync -av --exclude='.venv' --exclude='.git' --exclude='__pycache__' "$SDCARD_DIR"/ "$TERMUX_DIR"/
echo "✅ Folderi sinhronizovani"
echo ""

# Watch oba foldera istovremeno
sync_termux_to_sdcard() {
    local file="$1"
    local rel="${file#$TERMUX_DIR/}"
    
    # Preskoči exclude
    [[ "$rel" =~ ^\.venv ]] && return
    [[ "$rel" =~ ^\.git ]] && return
    [[ "$rel" =~ __pycache__ ]] && return
    
    local dst="$SDCARD_DIR/$rel"
    mkdir -p "$(dirname "$dst")"
    cp "$file" "$dst"
    echo "  📱→💾 $rel"
}

sync_sdcard_to_termux() {
    local file="$1"
    local rel="${file#$SDCARD_DIR/}"
    
    [[ "$rel" =~ ^\.venv ]] && return
    [[ "$rel" =~ ^\.git ]] && return
    [[ "$rel" =~ __pycache__ ]] && return
    
    local dst="$TERMUX_DIR/$rel"
    mkdir -p "$(dirname "$dst")"
    cp "$file" "$dst"
    echo "  💾→📱 $rel"
}

# Prati Termux folder
inotifywait -m -r -e modify,create,delete,move --format '%w%f' "$TERMUX_DIR" 2>/dev/null | while read file; do
    sync_termux_to_sdcard "$file"
done &

# Prati SDCARD folder
inotifywait -m -r -e modify,create,delete,move --format '%w%f' "$SDCARD_DIR" 2>/dev/null | while read file; do
    sync_sdcard_to_termux "$file"
done &

echo "👀 Watching... (Ctrl+C za prekid)"
echo "   Edituj u Acode na sdcard → pojavi se u Termux"
echo "   Edituj u Termux → pojavi se na sdcard"
echo ""

# Drži skriptu živom
trap 'kill $(jobs -p) 2>/dev/null; echo -e "\n👋 Zaustavljeno"' EXIT
wait
