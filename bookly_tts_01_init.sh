#!/bin/bash
# bookly_tts_01_init.sh
# Inicijalizacija BooklyTTS projekta

PROJECT_DIR="/sdcard/termux/BooklyTTS"

echo "================================================"
echo "  BooklyTTS - Inicijalizacija projekta (1/3)"
echo "================================================"
echo ""

# Kreiranje SVIH direktorija PRVO
echo "[1/7] Kreiranje strukture direktorija..."
mkdir -p "$PROJECT_DIR"/app/templates
mkdir -p "$PROJECT_DIR"/app/static/css
mkdir -p "$PROJECT_DIR"/app/static/js
mkdir -p "$PROJECT_DIR"/app/static/audio/chunks
mkdir -p "$PROJECT_DIR"/reference_audio
mkdir -p "$PROJECT_DIR"/uploads
mkdir -p "$PROJECT_DIR"/output
mkdir -p "$PROJECT_DIR"/library
mkdir -p "$PROJECT_DIR"/scripts
mkdir -p "$PROJECT_DIR"/tests

cd "$PROJECT_DIR" || exit 1
echo "  Direktoriji kreirani"

# .gitkeep fajlovi
touch app/static/audio/chunks/.gitkeep
touch uploads/.gitkeep
touch output/.gitkeep
touch library/.gitkeep

echo "[2/7] Kreiranje .gitignore..."
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
venv/
env/
.venv/
reference_audio/*.wav
reference_audio/*.mp3
reference_audio/*.flac
reference_audio/*.m4a
uploads/*
!uploads/.gitkeep
output/*
!output/.gitkeep
library/*
!library/.gitkeep
app/static/audio/chunks/*
!app/static/audio/chunks/.gitkeep
.env
.vscode/
.idea/
*.swp
*.log
ebook2audiobook/
epub2tts/
EOF
echo "  .gitignore kreiran"

echo "[3/7] Kreiranje README.md..."
cat > README.md << 'EOF'
# BooklyTTS

AI EPUB to Audiobook converter for HR/BS languages.

## Features
- Voice cloning from 10-30s reference audio
- EPUB parsing with chapters
- Flask Web UI + CLI
- XTTS-v2 backend (cs language)
- proot-distro Ubuntu on Android

## Quick Start
```bash
bash bookly_tts_01_init.sh
proot-distro login ubuntu
cd /sdcard/termux/BooklyTTS
bash bookly_tts_02_deps.sh
bash bookly_tts_03_app.sh
source venv/bin/activate
bash run_web.sh
EOF
echo "  README.md kreiran"

echo "[4/7] Kreiranje LICENSE..."
cat > LICENSE << 'EOF'
MIT License - BooklyTTS 2024
EOF
echo "  LICENSE kreiran"

echo "[5/7] Inicijalizacija git repozitorija..."
git init
echo "  Git init zavrsen"

echo "[6/7] Kreiranje inicijalnog commita..."
git add .
git commit -m "Initial commit: BooklyTTS project" 2>/dev/null
echo "  Commit zavrsen"

echo "[7/7] GitHub repozitorij..."
if command -v gh &> /dev/null; then
gh repo create "BooklyTTS" --public --source=. --remote=origin --push 2>/dev/null || echo "  GitHub repo vec postoji ili nema konekcije"
else
echo "  gh nije instaliran, preskacem GitHub"
fi

echo ""
echo "================================================"
echo "  INICIJALIZACIJA ZAVRSENA (1/3)"
echo "================================================"
echo ""
echo "  Sljedeci koraci:"
echo "  1. proot-distro login ubuntu"
echo "  2. cd /sdcard/termux/BooklyTTS"
echo "  3. bash bookly_tts_02_deps.sh"
echo ""


