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
