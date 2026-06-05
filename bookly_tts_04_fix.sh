#!/usr/bin/env bash
# ============================================================
# bookly_tts_04_fix.sh
# Ispravlja epub_fonetizator.py:
#   1. EPUB ZIP fallback (za fajlove koje ebooklib ne može parsirati)
#   2. Gemini graceful error handling (bez crash-a na non-JSON response)
#   3. Verbose debug output za AI greške
# Pokretanje: bash bookly_tts_04_fix.sh
# ============================================================
set -e

TOOL="epub_fonetizator.py"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $1"; }
info() { echo -e "${CYAN}[i]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

[[ -f "$TOOL" ]] || err "$TOOL nije pronađen u trenutnom direktoriju."

info "Patching $TOOL..."

# ════════════════════════════════════════════════════════════
# PATCH 1 — Zamijeni extract_text_from_epub s robusnom verzijom
# koja ima ZIP fallback kada ebooklib zakaže
# ════════════════════════════════════════════════════════════
python3 - << 'PATCH1'
import re

with open("epub_fonetizator.py", "r", encoding="utf-8") as f:
    src = f.read()

# Stari blok koji treba zamijeniti (od def extract_text_from_epub do kraja prve funkcije)
OLD = '''def extract_text_from_epub(epub_path: str) -> tuple[str, dict]:
    """
    Ekstraktuj sav tekst iz EPUB-a.
    Returns: (full_text, metadata)
    """
    if not EPUB_OK:
        raise RuntimeError("ebooklib ili beautifulsoup4 nisu instalirani.")

    book = epub.read_epub(epub_path)

    def get_meta(name):
        val = book.get_metadata("DC", name)
        return val[0][0] if val else "Nepoznato"

    meta = {
        "title":  get_meta("title"),
        "author": get_meta("creator"),
        "language": get_meta("language"),
    }

    all_text = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        try:
            html = item.get_content().decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "lxml")
            # Ukloni script/style
            for tag in ["script", "style", "nav", "head"]:
                for el in soup.find_all(tag):
                    el.decompose()
            text = soup.get_text(separator=" ")
            text = re.sub(r"\\s+", " ", text).strip()
            if len(text) > 20:
                all_text.append(text)
        except Exception:
            continue

    return " ".join(all_text), meta'''

NEW = '''def _extract_meta_from_opf(opf_content: str) -> dict:
    """Izvuci metapodatke iz OPF XML-a."""
    meta = {"title": "Nepoznato", "author": "Nepoznato", "language": "hr"}
    try:
        soup = BeautifulSoup(opf_content, "lxml-xml")
        for tag_name, key in [
            ("dc:title", "title"), ("title", "title"),
            ("dc:creator", "author"), ("creator", "author"),
            ("dc:language", "language"), ("language", "language"),
        ]:
            el = soup.find(tag_name)
            if el and el.get_text(strip=True):
                meta[key] = el.get_text(strip=True)
                break if key in ("title",) else None
    except Exception:
        pass
    return meta


def _html_to_clean_text(html_content: str) -> str:
    """Pretvori HTML u čisti tekst za NER."""
    try:
        soup = BeautifulSoup(html_content, "lxml")
        for tag in ["script", "style", "nav", "head"]:
            for el in soup.find_all(tag):
                el.decompose()
        text = soup.get_text(separator=" ")
        return re.sub(r"\\s+", " ", text).strip()
    except Exception:
        return ""


def _extract_via_zip(epub_path: str) -> tuple[str, dict]:
    """
    Fallback: čita EPUB direktno kao ZIP arhivu.
    Radi i kada ebooklib ne može naći container.xml.
    """
    import zipfile

    meta = {"title": "Nepoznato", "author": "Nepoznato", "language": "hr"}
    all_text = []

    with zipfile.ZipFile(epub_path, "r") as zf:
        names = zf.namelist()

        # Metapodaci iz OPF
        opf_files = [n for n in names if n.endswith(".opf")]
        if opf_files:
            try:
                opf = zf.read(opf_files[0]).decode("utf-8", errors="replace")
                meta = _extract_meta_from_opf(opf)
            except Exception:
                pass

        # Sva HTML/XHTML poglavlja — isključi toc/nav
        html_files = sorted([
            n for n in names
            if n.endswith((".html", ".xhtml", ".htm"))
            and not any(x in n.lower() for x in ("toc", "nav", "cover", "title-page"))
        ])

        # Ako OPF postoji, pokušaj dobiti redoslijed poglavlja iz spine
        ordered = []
        if opf_files:
            try:
                opf = zf.read(opf_files[0]).decode("utf-8", errors="replace")
                soup = BeautifulSoup(opf, "lxml-xml")
                # Izvuci itemref iz spine
                manifest = {}
                for item in soup.find_all("item"):
                    manifest[item.get("id", "")] = item.get("href", "")
                spine_items = [ref.get("idref", "") for ref in soup.find_all("itemref")]
                if spine_items:
                    opf_dir = "/".join(opf_files[0].split("/")[:-1])
                    for ref in spine_items:
                        href = manifest.get(ref, "")
                        if href:
                            full = (opf_dir + "/" + href).lstrip("/") if opf_dir else href
                            # Normalizuj putanju (ukloni ../)
                            parts = []
                            for p in full.split("/"):
                                if p == "..": parts.pop() if parts else None
                                elif p and p != ".": parts.append(p)
                            full = "/".join(parts)
                            if full in names:
                                ordered.append(full)
                if ordered:
                    html_files = ordered
            except Exception:
                pass

        for hf in html_files:
            try:
                content = zf.read(hf).decode("utf-8", errors="replace")
                text = _html_to_clean_text(content)
                if len(text) > 50:
                    all_text.append(text)
            except Exception:
                continue

    return " ".join(all_text), meta


def extract_text_from_epub(epub_path: str) -> tuple[str, dict]:
    """
    Ekstraktuj sav tekst iz EPUB-a.
    Pokušava ebooklib prvo; ako zakaže, koristi direktan ZIP pristup.
    Returns: (full_text, metadata)
    """
    if not EPUB_OK:
        raise RuntimeError("ebooklib ili beautifulsoup4 nisu instalirani.")

    # ── Pokušaj 1: ebooklib (standardni EPUB-ovi) ─────────────
    ebooklib_error = None
    try:
        book = epub.read_epub(epub_path)

        def get_meta(name):
            val = book.get_metadata("DC", name)
            return val[0][0] if val else "Nepoznato"

        meta = {
            "title":    get_meta("title"),
            "author":   get_meta("creator"),
            "language": get_meta("language"),
        }

        all_text = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                html = item.get_content().decode("utf-8", errors="replace")
                text = _html_to_clean_text(html)
                if len(text) > 20:
                    all_text.append(text)
            except Exception:
                continue

        full_text = " ".join(all_text)
        if len(full_text) > 200:
            logging.debug("EPUB parsiran via ebooklib")
            return full_text, meta

        # Ebooklib je vratio prazan tekst — probaj ZIP fallback
        ebooklib_error = "ebooklib vratio prazan tekst"

    except Exception as e:
        ebooklib_error = str(e)

    # ── Pokušaj 2: direktan ZIP pristup ───────────────────────
    logging.warning(f"ebooklib nije uspio ({ebooklib_error}), koristim ZIP fallback...")
    try:
        full_text, meta = _extract_via_zip(epub_path)
        if len(full_text) > 50:
            logging.info(f"ZIP fallback uspio: {len(full_text)} znakova")
            return full_text, meta
        raise RuntimeError("ZIP fallback vratio prazan tekst")
    except Exception as e2:
        raise RuntimeError(
            f"EPUB parsing potpuno zakazao.\\n"
            f"  ebooklib: {ebooklib_error}\\n"
            f"  ZIP:      {e2}\\n"
            f"  Provjeri da li je fajl validan EPUB: file '{epub_path}'"
        )'''

if OLD in src:
    src = src.replace(OLD, NEW)
    with open("epub_fonetizator.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("PATCH1 OK: EPUB ZIP fallback dodan")
else:
    print("PATCH1 SKIP: funkcija nije pronađena (već patchovana?)")
    # Provjeri da li je ZIP fallback već tu
    if "_extract_via_zip" in src:
        print("  → ZIP fallback već postoji, OK")
    else:
        print("  → UPOZORENJE: provjeri manuelno")
PATCH1

# ════════════════════════════════════════════════════════════
# PATCH 2 — Poboljšaj _call_gemini() sa graceful error handling
# ════════════════════════════════════════════════════════════
python3 - << 'PATCH2'
with open("epub_fonetizator.py", "r", encoding="utf-8") as f:
    src = f.read()

OLD = '''def _call_gemini(names: list[str], api_key: str, timeout: int = 30) -> Optional[dict]:
    """Pozovi Gemini API."""
    url = AI_CONFIG["gemini"]["url"] + f"?key={api_key}"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": SYSTEM_PROMPT + "\\n\\n" + _build_user_prompt(names)}]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048,
        }
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return _parse_json_response(text)
    except Exception as e:
        logging.debug(f"Gemini greška: {e}")
        return None'''

NEW = '''def _call_gemini(names: list[str], api_key: str, timeout: int = 30) -> Optional[dict]:
    """
    Pozovi Gemini API.
    Pokušava gemini-2.0-flash, a zatim gemini-1.5-flash kao fallback.
    """
    # Pokušaj sa oba modela
    models = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-2.5-flash",
    ]
    base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    for model in models:
        url = f"{base_url}/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": SYSTEM_PROMPT + "\\n\\n" + _build_user_prompt(names)}]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 2048,
            }
        }
        try:
            r = requests.post(url, json=payload, timeout=timeout)

            # Uvijek pokušaj pročitati response body — i za error statuse
            response_text = r.text
            try:
                data = r.json()
            except Exception:
                logging.debug(f"Gemini/{model} non-JSON response ({r.status_code}): {response_text[:200]}")
                continue  # Probaj sljedeći model

            if r.status_code != 200:
                err_msg = data.get("error", {}).get("message", response_text[:100])
                logging.debug(f"Gemini/{model} HTTP {r.status_code}: {err_msg}")
                # 404 = model ne postoji, probaj sljedeći
                # 400/403 = auth problem, nema smisla pokušavati druge modele
                if r.status_code in (400, 403):
                    logging.debug(f"Gemini auth/permission greška — odustajam od svih Gemini modela")
                    return None
                continue

            # Izvuci tekst iz candidates
            try:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                logging.debug(f"Gemini/{model} neočekivana struktura odgovora: {e}")
                logging.debug(f"  Response: {str(data)[:200]}")
                continue

            result = _parse_json_response(text)
            if result:
                logging.debug(f"Gemini/{model} uspješan")
                return result
            else:
                logging.debug(f"Gemini/{model} vratio nevalidan JSON: {text[:100]}")
                continue

        except requests.exceptions.Timeout:
            logging.debug(f"Gemini/{model} timeout ({timeout}s)")
            continue
        except requests.exceptions.ConnectionError as e:
            logging.debug(f"Gemini/{model} konekcija greška: {e}")
            return None  # Nema smisla pokušavati ako nema interneta
        except Exception as e:
            logging.debug(f"Gemini/{model} neočekivana greška: {e}")
            continue

    return None'''

if OLD in src:
    src = src.replace(OLD, NEW)
    with open("epub_fonetizator.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("PATCH2 OK: Gemini multi-model + graceful error handling")
else:
    print("PATCH2 SKIP: _call_gemini nije pronađen (već patchovan?)")
    if "models = [" in src and "gemini-1.5-flash" in src:
        print("  → Već patchovan, OK")
PATCH2

# ════════════════════════════════════════════════════════════
# PATCH 3 — Dodaj verbose AI error output u test meni
#           Prikaži HTTP status i error message korisniku
# ════════════════════════════════════════════════════════════
python3 - << 'PATCH3'
with open("epub_fonetizator.py", "r", encoding="utf-8") as f:
    src = f.read()

OLD = '''def _menu_test_ai(env_keys: dict):
    """Podizbornik: test AI konekcije."""
    test_names = ["John", "Shakespeare", "Paris", "Wolfgang", "Lejla", "Muhamed"]
    _log(f"\\n► Test fonetizacije: {test_names}", "cyan")

    for provider in PROVIDER_ORDER:
        api_key = get_api_key(provider, env_keys)
        if not api_key:
            _log(f"  {AI_CONFIG[provider][\'label\']}: nema ključa", "dim")
            continue

        _log(f"  Testiram {AI_CONFIG[provider][\'label\']}...", "yellow")

        if provider == "gemini":
            result = _call_gemini(test_names, api_key, timeout=20)
        else:
            result = _call_openai_compat(test_names, api_key, provider, timeout=20)

        if result:
            _log(f"  ✓ {AI_CONFIG[provider][\'label\']}: OK", "green")
            for k, v in list(result.items())[:4]:
                _log(f"    {k} → {v}", "white")
            break
        else:
            _log(f"  ✗ {AI_CONFIG[provider][\'label\']}: greška", "red")'''

NEW = '''def _menu_test_ai(env_keys: dict):
    """Podizbornik: test AI konekcije — testira SVE providere."""
    test_names = ["John", "Shakespeare", "Paris", "Wolfgang", "Lejla", "Muhamed"]
    _log(f"\\n► Test fonetizacije: {test_names}", "cyan")
    _log("  (testira sve dostupne providere, ne staje na prvom)\\n", "dim")

    # Uključi debug logging privremeno
    old_level = logging.getLogger().level
    logging.getLogger().setLevel(logging.DEBUG)

    any_ok = False
    for provider in PROVIDER_ORDER:
        api_key = get_api_key(provider, env_keys)
        label = AI_CONFIG[provider]["label"]

        if not api_key:
            _log(f"  ── {label}: nema ključa", "dim")
            continue

        _log(f"  ► Testiram {label}...", "yellow")

        try:
            if provider == "gemini":
                result = _call_gemini(test_names, api_key, timeout=25)
            else:
                result = _call_openai_compat(test_names, api_key, provider, timeout=25)
        except Exception as e:
            _log(f"  ✗ {label}: iznimka — {e}", "red")
            continue

        if result and isinstance(result, dict) and len(result) > 0:
            _log(f"  ✓ {label}: OK ({len(result)} fonetizacija)", "green")
            for k, v in list(result.items())[:4]:
                _log(f"      {k} → {v}", "white")
            any_ok = True
        else:
            _log(f"  ✗ {label}: vratio prazan/nevažeći odgovor", "red")
            _log(f"      (provjeri API ključ i quota na provideru)", "dim")

    logging.getLogger().setLevel(old_level)

    if not any_ok:
        _log("\\n  Ni jedan provider nije uspio!", "red")
        _log("  Provjeri:", "yellow")
        _log("    • API ključevi su tačni (opcija 2 u meniju)", "dim")
        _log("    • Internet konekcija radi", "dim")
        _log("    • Quota nije iscrpljena na providerima", "dim")
    else:
        _log("\\n  Fallback lanac spreman za upotrebu.", "green")'''

if OLD in src:
    src = src.replace(OLD, NEW)
    with open("epub_fonetizator.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("PATCH3 OK: test meni sada testira sve providere s debug outputom")
else:
    print("PATCH3 SKIP: _menu_test_ai nije pronađen ili već patchovan")
    if "any_ok" in src:
        print("  → Već patchovan, OK")
PATCH3

# ════════════════════════════════════════════════════════════
# PATCH 4 — Bolji error prikaz u _menu_fonetizuj za korisnike
#           Prikaži čitljiv error umjesto raw Python traceback
# ════════════════════════════════════════════════════════════
python3 - << 'PATCH4'
with open("epub_fonetizator.py", "r", encoding="utf-8") as f:
    src = f.read()

OLD = '''    _log(f"\\n► Ekstrahujem tekst iz: {Path(epub_path).name}", "cyan")
    try:
        text, meta = extract_text_from_epub(epub_path)
        _log(f"  Naslov: {meta[\'title\']}")
        _log(f"  Autor:  {meta[\'author\']}")
        _log(f"  Tekst:  {len(text)} znakova")
    except Exception as e:
        _log(f"✗ Greška pri parsiranju EPUB-a: {e}", "red")
        return'''

NEW = '''    _log(f"\\n► Ekstrahujem tekst iz: {Path(epub_path).name}", "cyan")
    try:
        text, meta = extract_text_from_epub(epub_path)
        _log(f"  Naslov: {meta[\'title\']}")
        _log(f"  Autor:  {meta[\'author\']}")
        _log(f"  Jezik:  {meta[\'language\']}")
        _log(f"  Tekst:  {len(text):,} znakova")
        if len(text) < 500:
            _log(f"  ⚠ Malo teksta ekstraktovano — EPUB možda ima nestandardnu strukturu", "yellow")
    except Exception as e:
        _log(f"✗ Greška pri parsiranju EPUB-a:", "red")
        # Prikaži svaki red greške zasebno za čitljivost
        for line in str(e).split("\\n"):
            if line.strip():
                _log(f"  {line.strip()}", "red" if "zakazao" in line else "yellow")
        _log("\\nSavjeti:", "cyan")
        _log("  • Provjeri da li je fajl otvoren u drugoj aplikaciji", "dim")
        _log("  • Pokušaj: unzip -t '" + epub_path + "' (provjera integriteta)", "dim")
        _log("  • Ako je fajl sa MoonReader-a, može imati DRM zaštitu", "dim")
        return'''

if OLD in src:
    src = src.replace(OLD, NEW)
    with open("epub_fonetizator.py", "w", encoding="utf-8") as f:
        f.write(src)
    print("PATCH4 OK: bolji error prikaz za EPUB greške")
else:
    print("PATCH4 SKIP: blok nije pronađen (već patchovan?)")
PATCH4

# ════════════════════════════════════════════════════════════
# Verifikacija
# ════════════════════════════════════════════════════════════
echo ""
info "Verifikujem patch..."
python3 -c "
import ast, sys
try:
    with open('epub_fonetizator.py') as f:
        src = f.read()
    ast.parse(src)
    print('  Sintaksa: OK')
    checks = [
        ('_extract_via_zip',     'ZIP fallback'),
        ('_html_to_clean_text',  'HTML helper'),
        ('gemini-1.5-flash',     'Gemini multi-model'),
        ('any_ok',               'Test all providers'),
        ('ZIP fallback uspio',   'ZIP logging'),
    ]
    for token, label in checks:
        status = '✓' if token in src else '✗'
        print(f'  {status} {label}')
except SyntaxError as e:
    print(f'  SINTAKSA GREŠKA: {e}')
    sys.exit(1)
"

echo ""
log "epub_fonetizator.py uspješno patchovan!"
echo ""
echo -e "${BOLD}Što je promijenjeno:${NC}"
echo -e "  ${CYAN}1.${NC} EPUB ZIP fallback — radi i kada ebooklib ne može naći container.xml"
echo -e "  ${CYAN}2.${NC} Gemini multi-model — probava gemini-2.0-flash, 1.5-flash, 2.5-flash"
echo -e "  ${CYAN}3.${NC} Graceful Gemini error — nema crash-a na non-JSON response"
echo -e "  ${CYAN}4.${NC} Test meni testira SVE providere s detaljnim debug outputom"
echo -e "  ${CYAN}5.${NC} Bolji EPUB error prikaz sa savjetima za korisnika"
echo ""
echo -e "Pokreni: ${YELLOW}python3 epub_fonetizator.py${NC}"
