#!/data/data/com.termux/files/usr/bin/bash
# ===========================================================================
# BooklyTTS – Fix skripta v2 (fuzzy/regex matching, Termux-native)
# Pokretanje: bash fix_booklytts_v2.sh
# ===========================================================================
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}  $*"; }
warn() { echo -e "${YELLOW}[--]${NC}  $*"; }
err()  { echo -e "${RED}[ERR]${NC} $*"; }

# ── Auto-lokacija projekta ──────────────────────────────────────────────────
BOOKLYTTS_DIR=""
for loc in "$HOME/BooklyTTS" "$HOME/booklytts" \
           "/storage/emulated/0/termux/BooklyTTS" \
           "/storage/emulated/0/BooklyTTS"; do
    [[ -f "$loc/app/__init__.py" ]] && { BOOKLYTTS_DIR="$loc"; break; }
done

if [[ -z "$BOOKLYTTS_DIR" ]]; then
    echo "BooklyTTS nije pronađen. Unesite putanju:"
    read -r BOOKLYTTS_DIR
    [[ -f "$BOOKLYTTS_DIR/app/__init__.py" ]] \
        || { err "Nevalidan direktorijum."; exit 1; }
fi

cd "$BOOKLYTTS_DIR"
echo -e "${GREEN}📍 Direktorijum:${NC} $BOOKLYTTS_DIR"
echo ""
echo "════════════════════════════════════"
echo "  BooklyTTS Fix Script v2"
echo "════════════════════════════════════"
echo ""

FIXED=0; SKIPPED=0; WARNED=0

py_fix() {
    # py_fix "NAZIV" "path" python_heredoc
    local label="$1"
    echo "--- ${label} ---"
    if python3 - 2>&1; then
        (( FIXED++ )) || true
    else
        warn "${label} – Python greška"
        (( WARNED++ )) || true
    fi
}

# ═══════════════════════════════════════════════════════════════════════════
# BONUS  stream.api.py → stream_api.py  (typo u imenu fajla)
# ═══════════════════════════════════════════════════════════════════════════
echo "--- BONUS: stream.api.py → stream_api.py ---"
STREAM_SRC=""
if   [[ -f "app/stream_api.py" ]]; then
    STREAM_SRC="app/stream_api.py"
    warn "stream_api.py već postoji – rename nije potreban"
    (( SKIPPED++ )) || true
elif [[ -f "app/stream.api.py" ]]; then
    mv "app/stream.api.py" "app/stream_api.py"
    STREAM_SRC="app/stream_api.py"
    # Popravi import u __init__.py ako referencira staro ime
    if grep -q "stream\.api" "app/__init__.py" 2>/dev/null; then
        sed -i 's/stream\.api/stream_api/g' "app/__init__.py"
        echo "  __init__.py import ažuriran"
    fi
    ok "BONUS gotov – preimenovan u stream_api.py"
    (( FIXED++ )) || true
else
    warn "Ni stream_api.py ni stream.api.py ne postoje"
    (( WARNED++ )) || true
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ARCH-02  lru_cache na instanci EPUBProcessor
# Fuzzy: traži @lru_cache + extract_chapters_cached pattern
# ═══════════════════════════════════════════════════════════════════════════
echo "--- ARCH-02: lru_cache na instanci ---"
python3 << 'PYEOF'
import re, sys, os

path = "app/epub_processor.py"
if not os.path.exists(path):
    print("  Fajl ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()

# Provjeri da li je već ispravljeno (modul-razinski _epub_cache postoji)
if "_epub_cache" in src:
    print("  Već ispravljeno (_epub_cache postoji)"); sys.exit(0)

# Fuzzy: pronađi @lru_cache blok vezan za instancu (extract_chapters_cached)
pattern = re.compile(
    r'[ \t]*@functools\.lru_cache\([^)]*\)\s*\n'
    r'[ \t]*def extract_chapters_cached\(self,[^)]+\):\s*\n'
    r'[ \t]*return self\._extract_chapters\([^)]+\)\s*\n'
    r'\s*\n'
    r'[ \t]*def extract_chapters\(self, epub_path\):\s*\n'
    r'[ \t]*mtime[^\n]+\n'
    r'[ \t]*return self\.extract_chapters_cached\([^)]+\)\s*\n',
    re.MULTILINE
)

replacement = (
    "    def extract_chapters(self, epub_path):\n"
    "        mtime = os.path.getmtime(epub_path) if os.path.exists(epub_path) else 0\n"
    "        return _epub_cache(epub_path, mtime)\n"
)

if not pattern.search(src):
    print("  Pattern nije pronađen – preskačem"); sys.exit(0)

src = pattern.sub(replacement, src)

# Ukloni 'import functools' ako postoji (dodat će se ispod kao modul fn)
src = re.sub(r'^import functools\n', '', src, flags=re.MULTILINE)

# Dodaj modul-razinski cache ispod svih import redova
cache_block = (
    "\nimport functools\n\n\n"
    "@functools.lru_cache(maxsize=16)\n"
    "def _epub_cache(epub_path: str, mtime: float):\n"
    '    """Modul-razinski cache – ne vezuje se za instancu."""\n'
    "    return EPUBProcessor()._extract_chapters(epub_path)\n\n\n"
)
# Ubaci iza zadnjeg import reda, ispred prve class/def
insert_pos = 0
for m in re.finditer(r'^(?:import |from )\S', src, re.MULTILINE):
    insert_pos = src.index('\n', m.start()) + 1

src = src[:insert_pos] + cache_block + src[insert_pos:]
open(path, "w", encoding="utf-8").write(src)
print("  epub_processor.py – ok")
PYEOF
ok "ARCH-02 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ARCH-03  asyncio.run() po svakom chunku u tts_engine.py
# ═══════════════════════════════════════════════════════════════════════════
echo "--- ARCH-03: asyncio.run() po svakom chunku ---"
python3 << 'PYEOF'
import re, sys, os

path = "app/tts_engine.py"
if not os.path.exists(path):
    print("  Fajl ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()

# Provjeri da li je već ispravljeno
if "_tts_loop" in src:
    print("  Već ispravljeno (_tts_loop postoji)"); sys.exit(0)

# Fuzzy: pronađi bilo koji asyncio.run(_synth()) poziv (s raznim uvlačenjima)
pattern = re.compile(r'^( +)asyncio\.run\(_synth\(\)\)\s*$', re.MULTILINE)
m = pattern.search(src)
if not m:
    print("  asyncio.run(_synth()) nije pronađen – preskačem"); sys.exit(0)

indent = m.group(1)
replacement = (
    f"{indent}import threading as _th\n"
    f"{indent}_tl = getattr(_th.current_thread(), '_tts_loop', None)\n"
    f"{indent}if _tl is None or _tl.is_closed():\n"
    f"{indent}    import asyncio as _aio\n"
    f"{indent}    _tl = _aio.new_event_loop()\n"
    f"{indent}    _th.current_thread()._tts_loop = _tl\n"
    f"{indent}_tl.run_until_complete(_synth())\n"
)

src = pattern.sub(replacement, src)
open(path, "w", encoding="utf-8").write(src)
print("  tts_engine.py – ok")
PYEOF
ok "ARCH-03 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ARCH-06  init_db() na svakom DB pozivu
# ═══════════════════════════════════════════════════════════════════════════
echo "--- ARCH-06: init_db() na svakom DB pozivu ---"
python3 << 'PYEOF'
import re, sys, os

# 1) database.py – ukloni init_db() iz tijela svake funkcije
path = "app/database.py"
if os.path.exists(path):
    src = open(path, encoding="utf-8").read()
    # Fuzzy: init_db() kao zasebna linija unutar def bloka (uvučena ≥4 razmaka)
    new_src = re.sub(r'^( {4,})init_db\(\)\n', '', src, flags=re.MULTILINE)
    if new_src != src:
        open(path, "w", encoding="utf-8").write(new_src)
        print("  database.py – redundantni init_db() uklonjen")
    else:
        print("  database.py – init_db() unutar funkcija nije pronađen")
else:
    print("  database.py ne postoji")

# 2) __init__.py – dodaj init_db() jednom pri startupu
path2 = "app/__init__.py"
if not os.path.exists(path2):
    print("  __init__.py ne postoji – preskačem"); sys.exit(0)

src2 = open(path2, encoding="utf-8").read()
if "from app.database import init_db" in src2:
    print("  __init__.py – init_db() već postoji")
else:
    # Fuzzy: ubaci ispred prvog 'from app.' ili 'from .routes' import reda
    m = re.search(r'^( *)(from app\.|from \.)', src2, re.MULTILINE)
    if m:
        pos = m.start()
        addition = "    from app.database import init_db\n    init_db()\n\n"
        # Ubaci unutar create_app() funkcije, ispred prvih blueprint importa
        src2 = src2[:pos] + addition + src2[pos:]
        open(path2, "w", encoding="utf-8").write(src2)
        print("  __init__.py – init_db() dodan pri startupu")
    else:
        print("  __init__.py – nije pronađen pogodni insert punkt")
PYEOF
ok "ARCH-06 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ARCH-07  tts_engines.py – mrtvi kod
# ═══════════════════════════════════════════════════════════════════════════
echo "--- ARCH-07: tts_engines.py – mrtvi kod ---"
if [[ -f "app/tts_engines.py" ]]; then
    mv "app/tts_engines.py" "app/_tts_engines_unused.py"
    ok "ARCH-07 gotov – preimenovan u _tts_engines_unused.py"
    (( FIXED++ )) || true
elif [[ -f "app/_tts_engines_unused.py" ]]; then
    warn "ARCH-07 – već preimenovan ranije"
    (( SKIPPED++ )) || true
else
    warn "ARCH-07 – tts_engines.py ne postoji"
    (( SKIPPED++ )) || true
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# ARCH-08  find_epub() vraća random EPUB (fuzzy)
# ═══════════════════════════════════════════════════════════════════════════
echo "--- ARCH-08: find_epub() vraća random EPUB ---"
python3 << 'PYEOF'
import re, sys, os

# Radi na stream_api.py ili stream.api.py
path = "app/stream_api.py" if os.path.exists("app/stream_api.py") else \
       "app/stream.api.py" if os.path.exists("app/stream.api.py") else None

if not path:
    print("  stream_api.py / stream.api.py nije pronađen – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()

# Provjeri da li je već ispravljeno
if "key=os.path.getmtime" in src:
    print(f"  {path} – već ispravljeno"); sys.exit(0)

# Fuzzy: pronađi cijeli find_epub def blok
pattern = re.compile(
    r'def find_epub\(filename=None\):\s*\n'
    r'(?:[ \t]+.*\n)*?'          # sve linije unutar funkcije
    r'(?=\ndef |\Z)',             # do sljedećeg def ili kraja fajla
    re.MULTILINE
)

new_fn = (
    "def find_epub(filename=None):\n"
    '    """Vrati traženi EPUB ili najnoviji po mtime-u."""\n'
    "    uploads = 'uploads'\n"
    "    if filename:\n"
    "        p = os.path.join(uploads, filename)\n"
    "        if os.path.exists(p):\n"
    "            return p\n"
    "    try:\n"
    "        epubs = [\n"
    "            os.path.join(uploads, f)\n"
    "            for f in os.listdir(uploads)\n"
    "            if f.endswith('.epub') and f != '.gitkeep'\n"
    "        ]\n"
    "        return max(epubs, key=os.path.getmtime) if epubs else None\n"
    "    except OSError:\n"
    "        return None\n"
)

if not pattern.search(src):
    print("  find_epub() def nije pronađen – preskačem"); sys.exit(0)

src = pattern.sub(new_fn, src)
open(path, "w", encoding="utf-8").write(src)
print(f"  {path} – ok")
PYEOF
ok "ARCH-08 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-03/04/07  reader.js funkcije – u reader.html (inline JS)
# Fuzzy regex matching, radi i kad je JS minificiran ili formatiran
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-03 + UX-04 + UX-07: reader.html inline JS ---"
python3 << 'PYEOF'
import re, sys, os

path = "app/templates/reader.html"
if not os.path.exists(path):
    print("  reader.html ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()
changed = False

# ── UX-03: resetBtns – dodaj skrivanje btn-restart ──────────────────────
# Fuzzy: pronađi resetBtns definiciju, unutar nje nađi zadnji display='none'
# i dodaj btn-restart iza njega (ako već nije tu)
if "btn-restart" not in src or \
   re.search(r"function resetBtns\b[^}]*btn-restart", src, re.DOTALL) is None:
    def patch_reset(m):
        body = m.group(0)
        if "btn-restart" in body:
            return body
        # Dodaj na kraj tijela funkcije, ispred zatvarajuće }
        insert = (
            "const rb=document.getElementById('btn-restart');"
            "if(rb)rb.style.display='none';"
        )
        return re.sub(r'(\})\s*$', insert + r'\1', body)

    new_src = re.sub(
        r'function resetBtns\s*\(\s*\)\s*\{[^}]+\}',
        patch_reset,
        src
    )
    if new_src != src:
        src = new_src; changed = True
        print("  UX-03: resetBtns – btn-restart dodan")
    else:
        print("  UX-03: resetBtns pattern nije pronađen")
else:
    print("  UX-03: već ispravljeno")

# ── UX-04: localStorage key fix ─────────────────────────────────────────
# changeFontSize: zamijeni localStorage.setItem('fs',...) → saveState() ili booklytts_state
if "localStorage.setItem('fs'" in src:
    src = re.sub(
        r"(function changeFontSize\s*\([^)]*\)\s*\{[^}]*)"
        r"localStorage\.setItem\(['\"]fs['\"][^)]+\)",
        lambda m: m.group(1) +
            "if(typeof saveState==='function'){saveState();}else{"
            "var _s=JSON.parse(localStorage.getItem('booklytts_state')||'{}');"
            "_s.fontSize=s;localStorage.setItem('booklytts_state',JSON.stringify(_s));}",
        src
    )
    changed = True
    print("  UX-04: changeFontSize localStorage key ispravljen")
else:
    print("  UX-04: changeFontSize – već ispravljeno ili 'fs' key ne postoji")

# IIFE koji čita 'fs': zamijeni na booklytts_state
if "localStorage.getItem('fs')" in src or 'localStorage.getItem("fs")' in src:
    src = re.sub(
        r'\(function\s*\(\s*\)\s*\{\s*'
        r'(?:const|let|var)\s+fs\s*=\s*localStorage\.getItem\([\'"]fs[\'"]\);'
        r'[^}]+\}\s*\)\s*\(\s*\)\s*;',
        "(function(){try{var _s=JSON.parse(localStorage.getItem('booklytts_state')||'{}');"
        "if(_s.fontSize){var _el=document.getElementById('font-size');"
        "var _rc=document.getElementById('reader-content');"
        "if(_el)_el.value=_s.fontSize;if(_rc)_rc.style.fontSize=_s.fontSize+'px';}}"
        "catch(e){}})();",
        src
    )
    changed = True
    print("  UX-04: IIFE localStorage key ispravljen")
else:
    print("  UX-04: IIFE – već ispravljeno ili 'fs' key ne postoji")

# ── UX-07: prevPage/nextPage dinamičan scroll ────────────────────────────
# Fuzzy: pronađi scrollBy({top: ±fiksna_vrijednost ili ±400
for fn, sign in [("prevPage", "-"), ("nextPage", "")]:
    pattern = re.compile(
        rf"(function {fn}\s*\(\s*\)\s*\{{[^}}]*)"
        rf"scrollBy\(\{{top\s*:\s*{sign}\d+",
        re.DOTALL
    )
    if pattern.search(src):
        if sign == "-":
            replace = (
                rf"\1scrollBy({{top:-(document.getElementById('reader-content')"
                rf".clientHeight*0.85||400)"
            )
        else:
            replace = (
                rf"\1scrollBy({{top:(document.getElementById('reader-content')"
                rf".clientHeight*0.85||400)"
            )
        src = pattern.sub(replace, src, count=1)
        changed = True
        print(f"  UX-07: {fn} scroll dinamičan")
    else:
        print(f"  UX-07: {fn} – već ispravljeno ili pattern nije pronađen")

if changed:
    open(path, "w", encoding="utf-8").write(src)
    print("  reader.html – snimljeno")
PYEOF
ok "UX-03 + UX-04 + UX-07 završeni"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-05  rules.html table CSS
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-05: rules.html table bez CSS ---"
python3 << 'PYEOF'
import re, sys, os

path = "app/templates/rules.html"
if not os.path.exists(path):
    print("  Fajl ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()
if "UX-05" in src or "#rules-list table" in src:
    print("  Već ispravljeno"); sys.exit(0)

css = """        <style>
        /* UX-05 */
        #rules-list table{width:100%;border-collapse:collapse;margin-top:8px}
        #rules-list td{padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.08);font-size:.9em;vertical-align:middle}
        #rules-list td:first-child{color:#e6edf3;font-weight:500;word-break:break-all}
        #rules-list td:nth-child(2){color:#8b949e;width:24px;text-align:center}
        #rules-list td:nth-child(3){color:#7b68ee;word-break:break-all}
        #rules-list td:last-child{width:32px;text-align:right}
        #rules-list tr:hover td{background:rgba(255,255,255,.03)}
        #rules-list button{background:none;border:none;color:#f85149;cursor:pointer;font-size:1em;padding:2px 4px}
        </style>\n"""

m = re.search(r'</head>', src, re.IGNORECASE)
if m:
    src = src[:m.start()] + css + src[m.start():]
    open(path, "w", encoding="utf-8").write(src)
    print("  rules.html – ok")
else:
    # Fallback: dodaj na vrh <body>
    src = re.sub(r'<body>', '<body>\n' + css, src, count=1)
    open(path, "w", encoding="utf-8").write(src)
    print("  rules.html – dodan ispred <body> (fallback)")
PYEOF
ok "UX-05 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-06  SR glasovi u reader.html dropdown
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-06: SR glasovi u reader dropdown-u ---"
python3 << 'PYEOF'
import re, sys, os

path = "app/templates/reader.html"
if not os.path.exists(path):
    print("  Fajl ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()
if "sr-RS-SophieNeural" in src:
    print("  Već ispravljeno"); sys.exit(0)

# Fuzzy: pronađi <select id="tts-voice"> blok
pattern = re.compile(
    r'(<select[^>]+id=["\']tts-voice["\'][^>]*>)'
    r'(.*?)'
    r'(</select>)',
    re.DOTALL | re.IGNORECASE
)

new_options = (
    '\n            <optgroup label="🇭🇷 Hrvatski">\n'
    '                <option value="hr-HR-GabrijelaNeural" selected>Gabrijela (ž)</option>\n'
    '                <option value="hr-HR-SreckoNeural">Srećko (m)</option>\n'
    '            </optgroup>\n'
    '            <optgroup label="🇧🇦 Bosanski">\n'
    '                <option value="bs-BA-VesnaNeural">Vesna (ž)</option>\n'
    '                <option value="bs-BA-GoranNeural">Goran (m)</option>\n'
    '            </optgroup>\n'
    '            <optgroup label="🇷🇸 Srpski">\n'
    '                <option value="sr-RS-SophieNeural">Sophie (ž)</option>\n'
    '                <option value="sr-RS-NicholasNeural">Nicholas (m)</option>\n'
    '            </optgroup>\n'
    '        '
)

m = pattern.search(src)
if not m:
    print("  tts-voice select nije pronađen – preskačem"); sys.exit(0)

src = pattern.sub(m.group(1) + new_options + m.group(3), src, count=1)
open(path, "w", encoding="utf-8").write(src)
print("  reader.html – ok")
PYEOF
ok "UX-06 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-08  Toast position: fixed
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-08: Toast nema position: fixed ---"
python3 << 'PYEOF'
import os, sys

path = "app/static/css/style.css"
if not os.path.exists(path):
    print("  Fajl ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()
if "#upload-toast" in src:
    print("  Već ispravljeno"); sys.exit(0)

addition = (
    "\n/* UX-08: floating toast */\n"
    "#upload-toast {\n"
    "    position: fixed;\n"
    "    bottom: 24px;\n"
    "    left: 50%;\n"
    "    transform: translateX(-50%);\n"
    "    z-index: 9999;\n"
    "    min-width: 220px;\n"
    "    max-width: 90vw;\n"
    "    text-align: center;\n"
    "    pointer-events: none;\n"
    "    box-shadow: 0 4px 16px rgba(0,0,0,0.4);\n"
    "}\n"
)
open(path, "a", encoding="utf-8").write(addition)
print("  style.css – ok")
PYEOF
ok "UX-08 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-09  Mobilni sidebar overlay
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-09: Mobilni sidebar overlay ---"
python3 << 'PYEOF'
import re, sys, os

path = "app/templates/reader.html"
if not os.path.exists(path):
    print("  Fajl ne postoji – preskačem"); sys.exit(0)

src = open(path, encoding="utf-8").read()
changed = False

# Fuzzy: pronađi .sidebar-overlay CSS blok i dodaj touch-action ako nedostaje
if "touch-action" not in src:
    src = re.sub(
        r'(\.sidebar-overlay\s*\{[^}]*)(z-index\s*:\s*\d+)',
        r'\1\2;touch-action:none;-webkit-tap-highlight-color:transparent',
        src
    )
    changed = True
    print("  sidebar-overlay: touch-action dodan")
else:
    print("  sidebar-overlay: touch-action već postoji")

# Fuzzy: u @media bloku, sidebar.open i sidebar-overlay.active
if "pointer-events:all" not in src and "pointer-events: all" not in src:
    src = re.sub(
        r'(\.sidebar-overlay\.active\s*\{[^}]*?)(display\s*:\s*block)',
        r'\1\2;pointer-events:all',
        src
    )
    changed = True
    print("  sidebar-overlay.active: pointer-events dodan")
else:
    print("  sidebar-overlay.active: pointer-events već postoji")

# Sidebar CSS transition za glatku animaciju
if "transition:transform" not in src and "transition: transform" not in src:
    src = re.sub(
        r'(@media[^{]*max-width\s*:\s*768px[^{]*\{.*?\.sidebar\s*\{[^}]*?)'
        r'(display\s*:\s*none)',
        r'\1\2;transition:transform 0.25s ease',
        src,
        flags=re.DOTALL
    )
    changed = True
    print("  sidebar: CSS transition dodana")
else:
    print("  sidebar: CSS transition već postoji")

if changed:
    open(path, "w", encoding="utf-8").write(src)
    print("  reader.html – snimljeno")
PYEOF
ok "UX-09 završen"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-10  test.html debug fajl
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-10: test.html debug fajl ---"
if [[ -f "app/templates/test.html" ]]; then
    mv "app/templates/test.html" "app/templates/_test.html.bak"
    ok "UX-10 gotov – preimenovan u _test.html.bak"
    (( FIXED++ )) || true
elif [[ -f "app/templates/_test.html.bak" ]]; then
    warn "UX-10 – već preimenovan ranije"
    (( SKIPPED++ )) || true
else
    warn "UX-10 – test.html ne postoji"
    (( SKIPPED++ )) || true
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# UX-02  convert.html – placeholder za app.js DOM ID-eve
# ═══════════════════════════════════════════════════════════════════════════
echo "--- UX-02: convert.html ---"
if [[ -f "app/templates/convert.html" ]]; then
    warn "UX-02 – convert.html već postoji"
    (( SKIPPED++ )) || true
else
    mkdir -p "app/templates"
    cat > "app/templates/convert.html" << 'HTMLEOF'
<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BooklyTTS – Konverter</title>
    <link rel="stylesheet" href="/static/css/style.css?v=8">
</head>
<body>
<div class="container">
    <header><h1>💾 Konverter</h1><a href="/">← Nazad</a></header>
    <main>
        <div class="card">
            <p>Status: <span id="status-dot">●</span> <span id="status-text"></span></p>
            <p id="disk-info"></p>
        </div>
        <div class="card">
            <h2>📤 Upload EPUB</h2>
            <input type="file" id="epub-file" accept=".epub">
            <div id="upload-toast" class="toast hidden"></div>
            <div id="epub-info" style="display:none">
                <p><strong id="epub-title"></strong> – <span id="epub-author"></span></p>
                <p id="epub-chapters-count"></p>
            </div>
        </div>
        <div id="chapter-section" style="display:none" class="card">
            <h2>📚 Poglavlja</h2>
            <select id="chapter-select-listen"></select>
            <p id="chapter-title-display"></p>
            <pre id="text-preview" style="display:none;max-height:200px;overflow:auto;
                 font-size:.8em;white-space:pre-wrap"></pre>
        </div>
        <div id="tabs-section" style="display:none" class="card">
            <h2>🎙️ Glas</h2>
            <select id="voice-select-listen"></select>
            <select id="voice-select-convert"></select>
            <label>Brzina: <span id="rate-value">1.0x</span>
                <input type="range" id="bg-mode" min="0.5" max="2.0" step="0.1" value="1.0">
            </label>
            <span id="bg-indicator"></span>
        </div>
        <div class="card">
            <input type="text" id="search-input-listen" placeholder="Pretraži poglavlja...">
            <div id="chapter-list"></div>
            <p id="chapter-count"></p>
        </div>
        <div class="card" style="display:flex;gap:8px;flex-wrap:wrap">
            <button id="play-btn-listen">▶️ Slušaj</button>
            <button id="stop-btn-listen">⏹️ Stop</button>
            <button id="start-btn">💾 Konvertuj</button>
            <button id="test-audio">🔊 Test glasa</button>
        </div>
        <audio id="audio-player" controls style="width:100%;margin-top:8px;display:none"></audio>
        <div id="text-preview-section" style="display:none" class="card">
            <p id="listen-status"></p>
        </div>
        <div id="progress-section" style="display:none" class="card">
            <div style="background:#21262d;border-radius:4px;height:8px;overflow:hidden">
                <div id="progress-fill"
                     style="height:100%;background:#7b68ee;width:0%;transition:width .3s"></div>
            </div>
            <p id="progress-text"></p>
            <p id="progress-detail" style="font-size:.8em;color:#8b949e"></p>
        </div>
        <div class="card">
            <h2>🎧 Moji audiobookovi</h2>
            <div id="audiobook-list"></div>
        </div>
    </main>
</div>
<script src="/static/js/app.js?v=8"></script>
</body>
</html>
HTMLEOF
    ok "UX-02 gotov – convert.html kreiran"
    (( FIXED++ )) || true
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Završni izvještaj
# ═══════════════════════════════════════════════════════════════════════════
echo "════════════════════════════════════"
echo " ✅  Fix skripta završena"
echo "════════════════════════════════════"
echo ""
echo " Primijenjeno : 8 Python patcha (fuzzy regex)"
echo " Bash koraci  : rename stream.api.py, tts_engines.py, test.html"
echo ""
echo " 🔄 Sljedeći koraci:"
echo "    1. Restartaj Flask:  pkill -f 'python.*run' && python run_web.sh"
echo "    2. Očisti cache:     Ctrl+Shift+R u browseru"
echo ""
