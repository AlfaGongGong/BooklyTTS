#!/usr/bin/env bash
# ============================================================
# bookly_tts_04_names.sh
# BooklyTTS — Instalacija i pokretanje EPUB fonetizatora
#
# Alat: epub_fonetizator.py
# Funkcija: NER ekstrakcija + AI fonetizacija HR/BS imena iz EPUB-a
# Output:   <ime_epub>.epub.replacement (pored EPUB fajla)
# Format:   original_ime#>#fonetizirano_ime
#
# Pokretanje: bash bookly_tts_04_names.sh
# ============================================================
set -e

PROJ_ROOT="/storage/emulated/0/termux/Skriptorij/BooklyTTS"
TOOL_NAME="epub_fonetizator.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo -e "\n${BOLD}═══ BooklyTTS — Fonetizator instalacija ═══${NC}\n"

# ─── Provjeri da li smo u proot Ubuntu ──────────────────────
if [ ! -f "/etc/debian_version" ] && [ ! -f "/etc/lsb-release" ]; then
  warn "Nije detektovan proot Ubuntu. Pokušavam svejedno..."
fi

# ─── Instaliraj Python zavisnosti ───────────────────────────
info "Instaliram Python pakete..."

pip3 install --quiet --break-system-packages \
  nltk \
  ebooklib \
  beautifulsoup4 \
  lxml \
  requests \
  rich \
  click \
  2>&1 | grep -E "(Successfully|already|ERROR)" || true

log "Python paketi instalirani"

# ─── Preuzmi NLTK podatke za NER ────────────────────────────
info "Preuzimam NLTK NER modele..."
python3 -c "
import nltk, ssl
ssl._create_default_https_context = ssl._create_unverified_context
for pkg in ['punkt_tab', 'averaged_perceptron_tagger_eng', 
            'maxent_ne_chunker_tab', 'words', 'stopwords']:
    try:
        nltk.download(pkg, quiet=True)
        print(f'  ✓ {pkg}')
    except Exception as e:
        print(f'  ✗ {pkg}: {e}')
"
log "NLTK modeli preuzeti"

# ─── Kopiraj alat u projekt ──────────────────────────────────
mkdir -p "$PROJ_ROOT"

# Provjeri postoji li već alat (generiran u ovoj skripti)
TOOL_PATH="$PROJ_ROOT/$TOOL_NAME"

if [ ! -f "$TOOL_PATH" ]; then
  # Alat se kreira u bookly_tts_04_tool.sh (2. skripta)
  warn "Alat $TOOL_NAME još nije kreiran."
  info "Pokreni: bash bookly_tts_04_tool.sh"
else
  log "Alat pronađen: $TOOL_PATH"
fi

# ─── Kreiraj .env.names template ako ne postoji ─────────────
ENV_FILE="$PROJ_ROOT/.env.names"
if [ ! -f "$ENV_FILE" ]; then
  cat > "$ENV_FILE" << 'ENVTEMPLATE'
# BooklyTTS — API ključevi za fonetizator
# Kopiraj ovaj fajl i popuni ključeve

# Gemini (primarni provider)
GEMINI_API_KEY=your_gemini_key_here

# Groq (fallback 1)
GROQ_API_KEY=your_groq_key_here

# Mistral (fallback 2)
MISTRAL_API_KEY=your_mistral_key_here

# GitHub Models (fallback 3)
GITHUB_TOKEN=your_github_token_here
ENVTEMPLATE
  warn "Kreiran $ENV_FILE — popuni API ključeve!"
else
  log ".env.names već postoji"
fi

# ─── Upute za pokretanje ────────────────────────────────────
echo ""
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Fonetizator spreman!${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "1. Popuni API ključeve:"
echo -e "   ${CYAN}nano $ENV_FILE${NC}"
echo ""
echo -e "2. Pokreni interaktivni meni:"
echo -e "   ${CYAN}cd $PROJ_ROOT && python3 $TOOL_NAME${NC}"
echo ""
echo -e "3. Ili direktno:"
echo -e "   ${CYAN}python3 $TOOL_NAME --epub knjiga.epub${NC}"
echo ""
echo -e "Output format: ${YELLOW}knjiga.epub.replacement${NC}"
echo -e "Svaki red:     ${YELLOW}ImeOriginal#>#ImeEFonetizirano${NC}"
echo ""
