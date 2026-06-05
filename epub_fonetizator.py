#!/usr/bin/env python3
# ============================================================
# epub_fonetizator.py
# BooklyTTS — EPUB NER ekstrakcija + AI fonetizacija HR/BS
#
# Workflow:
#   1. Parsiraj EPUB, izvuci sav tekst
#   2. NLTK NER + regex heuristika → lista kandidata za vlastita imena
#   3. Deduplikacija + filtriranje
#   4. AI refinement (Gemini→Groq→Mistral→GitHub) u batch-evima
#   5. Output: <epub>.replacement  (format: ime#>#fonetizirano)
#
# Upotreba:
#   python3 epub_fonetizator.py               ← interaktivni meni
#   python3 epub_fonetizator.py --epub k.epub ← direktno
#   python3 epub_fonetizator.py --help
# ============================================================

import os
import re
import sys
import json
import time
import click
import logging
import requests
from pathlib import Path
from collections import Counter
from typing import Optional
from bs4 import XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
# ── Pokušaj uvoziti rich; ako nedostaje, koristi fallback ──
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.prompt import Prompt, Confirm
    from rich import box
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    class _FallbackConsole:
        def print(self, *a, **kw): print(*a)
        def rule(self, t=""): print(f"\n{'─'*50} {t} {'─'*50}\n")
    console = _FallbackConsole()

# ── NLTK ───────────────────────────────────────────────────
try:
    import nltk
    from nltk import ne_chunk, pos_tag, word_tokenize, Tree
    from nltk.tokenize import sent_tokenize
    NLTK_OK = True
except ImportError:
    NLTK_OK = False

# ── EPUB ───────────────────────────────────────────────────
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    EPUB_OK = True
except ImportError:
    EPUB_OK = False


# ════════════════════════════════════════════════════════════
# KONSTANTE
# ════════════════════════════════════════════════════════════

VERSION = "1.0.0"
ENV_FILE = ".env.names"

# Fallback lanac providera
PROVIDER_ORDER = ["gemini", "groq", "mistral", "github"]

AI_CONFIG = {
    "gemini": {
        "url":     "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
        "env_key": "GEMINI_API_KEY",
        "label":   "Gemini 2.0 Flash",
    },
    "groq": {
        "url":     "https://api.groq.com/openai/v1/chat/completions",
        "env_key": "GROQ_API_KEY",
        "label":   "Groq",
        "model":   "llama-3.3-70b-versatile",
    },
    "mistral": {
        "url":     "https://api.mistral.ai/v1/chat/completions",
        "env_key": "MISTRAL_API_KEY",
        "label":   "Mistral",
        "model":   "mistral-large-latest",
    },
    "github": {
        "url":     "https://models.inference.ai.azure.com/chat/completions",
        "env_key": "GITHUB_TOKEN",
        "label":   "GitHub Models",
        "model":   "gpt-4o",
    },
}

BATCH_SIZE = 60  # imena po AI pozivu

# Regex za BS/HR vlastita imena (za dopunu NLTK-a)
# Hvata: Pero Perić, Nedžad, Lejla, itd.
NAME_REGEX = re.compile(
    r'\b([ÁČĆĐŠŽŽÉÀÜA-Z][a-záčćđšžžéàüa-z]{2,}'
    r'(?:\s+[ÁČĆĐŠŽŽÉÀÜA-Z][a-záčćđšžžéàüa-z]{2,}){0,3})\b'
)

# Blacklist — česte lažno-pozitivne riječi
BLACKLIST = {
    # ── Engleski članci, zamjenice, veznici, prijedlozi ──────────────────
    "The", "This", "That", "These", "Those", "There", "Their", "They",
    "When", "Where", "What", "Which", "While", "Whose", "Whether",
    "With", "From", "Into", "Upon", "Then", "Thus", "Also", "Such",
    "Each", "Both", "Some", "Many", "Most", "More", "Less", "Very",
    "Just", "Only", "Even", "Still", "Again", "Always", "Never",
    "Here", "Now", "Once", "After", "Before", "Until", "Since",
    "About", "Above", "Below", "Behind", "Beside", "Between", "Beyond",
    "Under", "Over", "Through", "Across", "Along", "Around", "Against",
    "Because", "Although", "However", "Therefore", "Perhaps", "Maybe",
    "Could", "Would", "Should", "Might", "Shall", "Will", "Have",
    "Been", "Being", "Done", "Made", "Said", "Came", "Went", "Took",
    "Knew", "Told", "Came", "Gave", "Left", "Kept", "Felt", "Seen",
    "Than", "Then", "Another", "Other", "Every", "Little", "Well",
    "First", "Last", "Next", "Long", "Great", "Good", "High", "Old",
    "New", "Same", "Small", "Large", "Own", "Right", "Early", "Far",
    "Hard", "Night", "Day", "Time", "Hand", "Part", "Place", "Case",
    "Back", "Thing", "Man", "Men", "Woman", "People", "Way", "Life",
    "Head", "Face", "Body", "Eye", "Eyes", "Word", "Work", "Point",
    "War", "World", "Lord", "Lady", "King", "Queen", "Prince", "Guard",
    "North", "South", "East", "West", "Company", "Black", "White",
    "Dark", "Light", "Dead", "Death", "Blood", "Fire", "Water", "Gold",
    "Army", "City", "Land", "Camp", "Gate", "Wall", "Road", "Line",
    "They", "Them", "Their", "Him", "Her", "His", "Its", "Our", "Your",
    # ── HR/BS česte lažno-pozitivne ──────────────────────────────────────
    "Kada", "Gdje", "Kako", "Zašto", "Zatim", "Prema", "Kroz",
    "Nakon", "Između", "Ispred", "Iza", "Iznad", "Ispod", "Pored",
    "Više", "Manje", "Svaki", "Svaka", "Svako", "Njegova", "Njezina",
    "Njeno", "Njihov", "Njihova", "Čovjek", "Žena", "Djeca", "Ljudi",
    "Ovaj", "Ova", "Ovo", "Onaj", "Ona", "Ono", "Koji", "Koja", "Koje",
    "Neki", "Neka", "Neko", "Jedan", "Jedna", "Jedno", "Drugi", "Druga",
    "Prvo", "Drugi", "Treći", "Veliki", "Mala", "Malo", "Novi", "Nova",
    "Bio", "Bila", "Bilo", "Jest", "Nije", "Biti", "Imati", "Moći",
    "Kao", "Ali", "Ako", "Jer", "Dok", "Tek", "Već", "Još", "Ili",
    "Niti", "Nego", "Mada", "Iako", "Budući", "Čim", "Sve", "Sam",
    "Može", "Mora", "Treba", "Htio", "Htjeti", "Rekao", "Reče",
    "Tada", "Sada", "Ovdje", "Tamo", "Ovuda", "Onuda", "Nikad",
    "Uvijek", "Opet", "Samo", "Čak", "Baš", "Upravo", "Ipak",
    "Pošto", "Budući", "Premda", "Svakako", "Možda", "Gotovo",
    "Mnogi", "Mnoga", "Cijeli", "Cijela", "Cijelo", "Drugi", "Svaki",
    "Tog", "Taj", "Toj", "Tome", "Toga", "Tim", "Tih", "Toj",
    # ── Dani i mjeseci ───────────────────────────────────────────────────
    "Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja",
    "Januar", "Februar", "Mart", "April", "Maj", "Juni", "Juli",
    "August", "Septembar", "Oktobar", "Novembar", "Decembar",
    "Siječanj", "Veljača", "Ožujak", "Travanj", "Svibanj", "Lipanj",
    "Srpanj", "Kolovoz", "Rujan", "Listopad", "Studeni", "Prosinac",
    # ── Titule i funkcije ────────────────────────────────────────────────
    "Doktor", "Profesor", "General", "Kapetan", "Pukovnik", "Major",
    "Poručnik", "Narednik", "Vojnik", "Zapovjednik", "Časnik",
    "Doctor", "Captain", "Colonel", "Lieutenant", "Sergeant", "Master",
    "Mister", "Mistress", "Brother", "Sister", "Father", "Mother",
}

# Minimalna dužina imena
MIN_NAME_LEN = 3
MIN_FREQ = 2  # koliko puta se mora pojaviti da ne bude odbačeno


# ════════════════════════════════════════════════════════════
# ENV LOADER
# ════════════════════════════════════════════════════════════

def load_env(env_path: str = ENV_FILE) -> dict:
    """Učitaj API ključeve iz .env.names fajla i OS okoline."""
    keys = {}

    # Prvo pokušaj .env.names
    env_file = Path(env_path)
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    v = v.strip()
                    if v and not v.startswith("your_"):
                        keys[k.strip()] = v

    # OS okolina ima prednost
    for provider, cfg in AI_CONFIG.items():
        env_key = cfg["env_key"]
        if os.environ.get(env_key):
            keys[env_key] = os.environ[env_key]

    return keys


def get_api_key(provider: str, env_keys: dict) -> Optional[str]:
    """Vrati API ključ za zadani provider."""
    env_key = AI_CONFIG[provider]["env_key"]
    return env_keys.get(env_key)


# ════════════════════════════════════════════════════════════
# EPUB PARSER
# ════════════════════════════════════════════════════════════

def _extract_meta_from_opf(opf_content: str) -> dict:
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
                if key == "title":
                    break
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
        return re.sub(r"\s+", " ", text).strip()
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
            f"EPUB parsing potpuno zakazao.\n"
            f"  ebooklib: {ebooklib_error}\n"
            f"  ZIP:      {e2}\n"
            f"  Provjeri da li je fajl validan EPUB: file '{epub_path}'"
        )


# ════════════════════════════════════════════════════════════
# NER EKSTRAKCIJA
# ════════════════════════════════════════════════════════════

def _nltk_ner(text: str, verbose: bool = False) -> set[str]:
    """NLTK NER — radi na engleskom ali hvata mnoga vlastita imena."""
    if not NLTK_OK:
        return set()

    names = set()
    # Radi na kraćim segmentima (NLTK je spor na dugim tekstovima)
    # Uzmi max 50000 znakova za NER (uzorak)
    if verbose:
        _log(f"  NER: obrađujem {min(len(text), 50000):,}/{len(text):,} znakova...", "dim")
    sample = text[:50000] if len(text) > 50000 else text

    try:
        sentences = sent_tokenize(sample)
        for sent in sentences:
            try:
                if verbose and sent_idx % 200 == 0 and sent_idx > 0:
                    _log(f"  NER: {sent_idx}/{len(sentences)} rečenica, "
                         f"{len(names)} imena do sad...", "dim")
                tokens  = word_tokenize(sent)
                tagged  = pos_tag(tokens)
                chunked = ne_chunk(tagged, binary=False)
                for subtree in chunked:
                    if isinstance(subtree, Tree) and subtree.label() in (
                        "PERSON", "GPE", "ORGANIZATION", "FACILITY", "GSP"
                    ):
                        name = " ".join(word for word, _ in subtree.leaves())
                        if len(name) >= MIN_NAME_LEN:
                            names.add(name)
            except Exception:
                continue
    except Exception:
        pass

    return names


def _regex_ner(text: str) -> Counter:
    """
    Regex heuristika za BS/HR vlastita imena.
    Bilježi frekvenciju pojave.
    """
    candidates = Counter()
    matches = NAME_REGEX.findall(text)
    for m in matches:
        m = m.strip()
        if (len(m) >= MIN_NAME_LEN
                and m not in BLACKLIST
                and not m.isupper()
                and not m[0].isdigit()):
            candidates[m] += 1
    return candidates


# Skup čestih engleskih common words napisanih velikim slovom
# (dopuna BLACKLIST-i za _is_likely_name provjeru)
_COMMON_WORDS_EN = {
    w.lower() for w in [
        "The", "This", "That", "These", "Those", "There", "Their",
        "When", "Where", "What", "Which", "While", "With", "From",
        "Into", "Upon", "Then", "Thus", "Also", "Such", "Each", "Both",
        "Some", "Many", "Most", "More", "Less", "Very", "Just", "Only",
        "Even", "Still", "Again", "Always", "Never", "Here", "Now",
        "Once", "After", "Before", "Until", "Since", "About", "Above",
        "Below", "Behind", "Because", "Although", "However", "Could",
        "Would", "Should", "Might", "Have", "Been", "Being", "Done",
        "Made", "Said", "Came", "Went", "Took", "Another", "Other",
        "Every", "Little", "Well", "First", "Last", "Next", "Long",
        "Great", "Good", "High", "Old", "New", "Same", "Small", "Large",
        "Night", "Time", "Hand", "Part", "Place", "Thing", "People",
        "North", "South", "East", "West", "Company", "Black", "White",
        "Dark", "Light", "Dead", "Death", "Blood", "Fire", "Water",
        "Army", "City", "Land", "Camp", "Gate", "Wall", "Road", "Line",
        "Lord", "Lady", "King", "Queen", "Guard", "Prince", "War",
    ]
}


def _is_likely_name(token: str) -> bool:
    """
    Dodatne heuristike da li je token vlastito ime.
    Odbacuje česte lažno-pozitivne.
    """
    # Odbaci ako sadrži samo velika slova (akronim)
    if token.isupper():
        return False
    # Odbaci česte engleske common words (case-insensitive)
    if token.lower() in _COMMON_WORDS_EN:
        return False
    # Odbaci ako je prijedlog ili veznik (mala lista)
    stopwords_hr = {
        "Ali", "Ako", "Jer", "Dok", "Tek", "Već", "Još", "Ili",
        "Niti", "Nego", "Mada", "Iako", "Budući", "Čim", "Sve",
        "Kao", "Bio", "Bila", "Bilo", "Taj", "Tog", "Toj", "Tome",
        "Ovaj", "Ova", "Ovo", "Oni", "One", "Ona", "Jedan", "Jedna",
    }
    if token in stopwords_hr:
        return False
    # Mora počinjati velikim slovom
    if not token[0].isupper():
        return False
    # Odbaci jednoznakovne
    if len(token) < 2:
        return False
    return True


def extract_names(text: str, verbose: bool = False) -> list[str]:
    """
    Kombinirani NER: NLTK + regex heuristika.
    Returns: sortirana lista jedinstvenih kandidata za vlastita imena.
    """
    if verbose:
        console.print("[cyan]► Pokrećem NLTK NER...[/]" if RICH else "► NLTK NER...")

    nltk_names = _nltk_ner(text, verbose=verbose)

    if verbose:
        console.print(f"  NLTK pronašao: {len(nltk_names)} entiteta")
        console.print("[cyan]► Pokrećem regex heuristiku...[/]" if RICH else "► Regex...")

    regex_counts = _regex_ner(text)

    # Spoji: NLTK rezultati se uvijek uključuju (pouzdan NER)
    # Regex: uključi samo ako se pojavljuje barem MIN_FREQ puta
    all_names = set(nltk_names)
    for name, count in regex_counts.items():
        if count >= MIN_FREQ and _is_likely_name(name):
            all_names.add(name)

    # Finalno filtriranje
    filtered = []
    for name in all_names:
        name = name.strip()
        if (name
                and len(name) >= MIN_NAME_LEN
                and name not in BLACKLIST
                and _is_likely_name(name)):
            filtered.append(name)

    # Sortiraj — abecedno
    filtered.sort()

    if verbose:
        console.print(f"  Ukupno kandidata nakon filtriranja: {len(filtered)}")

    return filtered


# ════════════════════════════════════════════════════════════
# AI PROVIDERS
# ════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Ti si stručnjak za fonetizaciju vlastitih imena za TTS (text-to-speech) sustave koji govore bosanskim i hrvatskim jezikom koristeći XTTS-v2 model.

Zadatak: Za svako dato vlastito ime (osoba, mjesto, organizacija), napiši fonetski zapis kako TREBA biti izgovoreno na bosanskom/hrvatskom jeziku.

Pravila fonetizacije:
- Strana imena pišemo fonetski onako kako bi ih čitač glasno izgovorio na BS/HR
- Domaća BS/HR/SRB imena ostaju ista ili se blago prilagode izgovoru
- Engleski: 'John' → 'Džon', 'William' → 'Vilijam', 'Shakespeare' → 'Šekspir'
- Francuski: 'Jacques' → 'Žak', 'Beaumont' → 'Bomon'
- Njemački: 'Wolfgang' → 'Volfgang', 'Schmidt' → 'Šmit'
- Talijanski: 'Giovanni' → 'Đovani', 'Venezia' → 'Venecija'
- Ruska/slavenska: Ostavi uglavnom kako jesu, prilagodi grafiju
- Ako ime već jest fonetski ispravno u BS/HR grafiji, vrati ga nepromijenjeno
- Ne mijenjaj interpunkciju, redne brojeve, akronime

Format odgovora: ISKLJUČIVO JSON objekt bez ikakvog dodatnog teksta, bez markdown fence:
{"ImeOriginal": "fonetizovano_ime", "ImeOriginal2": "fonetizovano_ime2"}

Primjeri:
Ulaz: John, Sarajevo, Shakespeare, Lejla, Paris, Wolfgang, Đorđe
Izlaz: {"John": "Džon", "Sarajevo": "Sarajevo", "Shakespeare": "Šekspir", "Lejla": "Lejla", "Paris": "Pari", "Wolfgang": "Volfgang", "Đorđe": "Đorđe"}"""


def _build_user_prompt(names: list[str]) -> str:
    return "Fonetizuj sljedeća vlastita imena:\n" + ", ".join(names)


def _call_gemini(names: list[str], api_key: str, timeout: int = 30) -> Optional[dict]:
    """
    Pozovi Gemini API.
    Pokušava gemini-2.0-flash, a zatim gemini-1.5-flash kao fallback.
    """
    # Pokušaj sa oba modela
    models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
    ]
    base_url = "https://generativelanguage.googleapis.com/v1beta/models"

    for model in models:
        url = f"{base_url}/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": SYSTEM_PROMPT + "\n\n" + _build_user_prompt(names)}]
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

    return None


def _call_openai_compat(
    names: list[str], api_key: str, provider: str, timeout: int = 30
) -> Optional[dict]:
    """Generički OpenAI-compatible API poziv (Groq, Mistral, GitHub)."""
    cfg   = AI_CONFIG[provider]
    model = cfg.get("model", "gpt-4o")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": _build_user_prompt(names)},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    }
    try:
        r = requests.post(cfg["url"], headers=headers, json=payload, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]
        return _parse_json_response(text)
    except Exception as e:
        logging.debug(f"{provider} greška: {e}")
        return None


def _parse_json_response(text: str) -> Optional[dict]:
    """Parsiraj JSON iz AI odgovora, robustno."""
    # Ukloni markdown fence ako postoji
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    text = text.strip()

    # Pokušaj direktni parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Pokušaj izvuci JSON objekt regex-om
    match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def ai_phonetize_batch(
    names: list[str],
    env_keys: dict,
    provider_order: list[str] = None,
    verbose: bool = False,
) -> tuple[dict, str]:
    """
    Fonetizuj listu imena kroz AI fallback lanac.
    Returns: (rezultati_dict, provider_koji_je_uspio)
    """
    if provider_order is None:
        provider_order = PROVIDER_ORDER

    for provider in provider_order:
        api_key = get_api_key(provider, env_keys)
        if not api_key:
            if verbose:
                _log(f"  {provider}: nema API ključa, preskačem", "yellow")
            continue

        label = AI_CONFIG[provider]["label"]
        if verbose:
            _log(f"  Pokušavam {label}...", "cyan")

        if provider == "gemini":
            result = _call_gemini(names, api_key)
        else:
            result = _call_openai_compat(names, api_key, provider)

        if result and isinstance(result, dict):
            if verbose:
                _log(f"  ✓ {label} odgovorio ({len(result)} fonetizacija)", "green")
            return result, provider
        else:
            if verbose:
                _log(f"  ✗ {label} nije vratio validan odgovor", "red")
        # Kratka pauza između pokušaja
        time.sleep(0.5)

    return {}, "none"


def phonetize_all(
    names: list[str],
    env_keys: dict,
    batch_size: int = BATCH_SIZE,
    verbose: bool = False,
) -> dict:
    """
    Fonetizuj sve kandidate u batch-evima.
    Returns: dict {original: fonetizovano}
    """
    all_results = {}
    total_batches = (len(names) + batch_size - 1) // batch_size

    if verbose:
        console.print(
            f"\n[bold cyan]AI fonetizacija:[/] {len(names)} imena, "
            f"{total_batches} batch-eva (veličina {batch_size})"
            if RICH else
            f"\nAI fonetizacija: {len(names)} imena, {total_batches} batch-eva"
        )

    for i in range(0, len(names), batch_size):
        batch = names[i:i + batch_size]
        batch_num = i // batch_size + 1

        if verbose:
            preview = ", ".join(batch[:5])
            suffix  = f"... +{len(batch)-5}" if len(batch) > 5 else ""
            _log(f"\n─ Batch {batch_num}/{total_batches} "
                 f"({len(batch)} imena): {preview}{suffix}", "cyan")

        result, provider = ai_phonetize_batch(batch, env_keys, verbose=verbose)

        # Progress: koji provider je odgovorio
        if verbose:
            if result:
                hit  = sum(1 for n in batch if result.get(n, n) != n)
                _log(f"  ✓ Batch {batch_num}/{total_batches} → {provider or '?'} "
                     f"({hit}/{len(batch)} fonetizovano)", "green")
            else:
                _log(f"  ✗ Batch {batch_num}/{total_batches} → svi provideri zakazali", "red")

        # Za svako ime iz batcha — ako AI nije vratio, zadrži originalno
        for name in batch:
            phonetic = result.get(name, name)
            # Sanitizacija: ukloni eventualne navodnike
            phonetic = phonetic.strip().strip('"').strip("'")
            all_results[name] = phonetic

        # Rate limiting — malo pauze između batch-eva
        if i + batch_size < len(names):
            time.sleep(0.8)

    return all_results


# ════════════════════════════════════════════════════════════
# OUTPUT WRITER
# ════════════════════════════════════════════════════════════

def write_replacement_file(
    epub_path: str,
    phonetics: dict,
    output_path: Optional[str] = None,
) -> str:
    """
    Zapiši .replacement fajl pored EPUB-a.
    Format po liniji: original#>#fonetizovano
    Preskače parove gdje je original == fonetizovano.
    """
    epub_p = Path(epub_path).resolve()

    if output_path:
        out_p = Path(output_path)
    else:
        out_p = epub_p.parent / (epub_p.name + ".replacement")

    lines = []
    for original, phonetic in sorted(phonetics.items()):
        original = original.strip()
        phonetic = phonetic.strip()
        # Zapiši i identične — korisnik može sam procijeniti
        if original and phonetic:
            lines.append(f"{original}#>#{phonetic}")

    with open(out_p, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        if lines:
            f.write("\n")

    return str(out_p)


# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════

def _log(msg: str, color: str = "white"):
    if RICH:
        console.print(f"[{color}]{msg}[/]")
    else:
        print(msg)


def _print_banner():
    banner = (
        "\n╔═══════════════════════════════════════════╗\n"
        "║  BooklyTTS · EPUB Fonetizator  v" + VERSION + "    ║\n"
        "║  NER + NLTK + AI (Gemini→Groq→Mistral)   ║\n"
        "╚═══════════════════════════════════════════╝\n"
    )
    if RICH:
        console.print(Panel(banner.strip(), border_style="cyan"))
    else:
        print(banner)


def _check_dependencies():
    """Provjeri sve zavisnosti i javi što nedostaje."""
    missing = []
    if not EPUB_OK:
        missing.append("ebooklib  (pip install ebooklib)")
    if not NLTK_OK:
        missing.append("nltk      (pip install nltk)")
    if missing:
        _log("Nedostaju zavisnosti:", "red")
        for m in missing:
            _log(f"  pip install {m}", "yellow")
        return False
    return True


def _check_nltk_data():
    """Provjeri da li su NLTK NER podaci preuzeti."""
    required = [
        ("tokenizers/punkt_tab", "punkt_tab"),
        ("taggers/averaged_perceptron_tagger_eng", "averaged_perceptron_tagger_eng"),
        ("chunkers/maxent_ne_chunker_tab", "maxent_ne_chunker_tab"),
        ("corpora/words", "words"),
    ]
    for path, pkg in required:
        try:
            nltk.data.find(path)
        except LookupError:
            _log(f"Preuzimam NLTK paket: {pkg}...", "yellow")
            try:
                import ssl
                ssl._create_default_https_context = ssl._create_unverified_context
                nltk.download(pkg, quiet=True)
            except Exception as e:
                _log(f"  ✗ Nije moguće preuzeti {pkg}: {e}", "red")


def _show_preview(names: list[str], phonetics: dict, max_rows: int = 20):
    """Prikaži preview rezultata."""
    if RICH:
        table = Table(title="Preview fonetizacije", box=box.ROUNDED, border_style="cyan")
        table.add_column("Originalno", style="white")
        table.add_column("Fonetizirano", style="green")
        table.add_column("Status", style="dim")
        for name in names[:max_rows]:
            phonetic = phonetics.get(name, name)
            changed = "✓ promijenjeno" if phonetic != name else "─ isto"
            style = "green" if phonetic != name else "dim"
            table.add_row(name, phonetic, f"[{style}]{changed}[/]")
        if len(names) > max_rows:
            table.add_row(f"... i još {len(names) - max_rows}", "", "")
        console.print(table)
    else:
        print(f"\n{'─'*50}")
        print(f"{'ORIGINALNO':<30} {'FONETIZIRANO'}")
        print(f"{'─'*50}")
        for name in names[:max_rows]:
            phonetic = phonetics.get(name, name)
            print(f"{name:<30} {phonetic}")
        if len(names) > max_rows:
            print(f"... i još {len(names) - max_rows}")
        print(f"{'─'*50}\n")


# ════════════════════════════════════════════════════════════
# INTERAKTIVNI MENI
# ════════════════════════════════════════════════════════════

def interactive_menu(env_keys: dict):
    """Interaktivni CLI meni za fonetizator."""
    _print_banner()

    while True:
        if RICH:
            console.rule("[bold cyan]Glavni izbornik[/]")
            console.print(
                "\n[bold]1.[/] Fonetizuj EPUB\n"
                "[bold]2.[/] Prikaži/ureduj API ključeve\n"
                "[bold]3.[/] Test AI konekcije\n"
                "[bold]4.[/] Pregledaj .replacement fajl\n"
                "[bold]5.[/] Izlaz\n"
            )
            choice = Prompt.ask("[cyan]Odabir[/]", choices=["1","2","3","4","5"])
        else:
            print("\n═══ IZBORNIK ═══")
            print("1. Fonetizuj EPUB")
            print("2. Prikaži/ureduj API ključeve")
            print("3. Test AI konekcije")
            print("4. Pregledaj .replacement fajl")
            print("5. Izlaz")
            choice = input("Odabir: ").strip()

        if choice == "1":
            _menu_fonetizuj(env_keys)
        elif choice == "2":
            env_keys = _menu_api_keys(env_keys)
        elif choice == "3":
            _menu_test_ai(env_keys)
        elif choice == "4":
            _menu_pregledaj()
        elif choice == "5":
            _log("\nDoviđenja!", "cyan")
            sys.exit(0)


def _menu_fonetizuj(env_keys: dict):
    """Podizbornik: fonetizacija EPUB-a."""
    if RICH:
        epub_path = Prompt.ask("[cyan]Putanja do EPUB fajla[/]").strip()
    else:
        epub_path = input("Putanja do EPUB: ").strip()

    epub_path = epub_path.strip("'\"")  # ukloni navodnike ako je drag-and-drop

    if not Path(epub_path).exists():
        _log(f"✗ Fajl nije pronađen: {epub_path}", "red")
        return

    if not epub_path.lower().endswith(".epub"):
        _log("✗ Fajl mora biti .epub format", "red")
        return

    # Opcije
    if RICH:
        batch_input = Prompt.ask(
            "[cyan]Veličina batch-a za AI[/]",
            default=str(BATCH_SIZE)
        )
        verbose = Confirm.ask("[cyan]Detaljan ispis?[/]", default=True)
    else:
        batch_input = input(f"Batch veličina [{BATCH_SIZE}]: ").strip() or str(BATCH_SIZE)
        verbose_in  = input("Detaljan ispis? [Y/n]: ").strip().lower()
        verbose = verbose_in != "n"

    try:
        batch = int(batch_input)
    except ValueError:
        batch = BATCH_SIZE

    # Pipeline
    _log(f"\n► Ekstrahujem tekst iz: {Path(epub_path).name}", "cyan")
    try:
        text, meta = extract_text_from_epub(epub_path)
        _log(f"  Naslov: {meta['title']}")
        _log(f"  Autor:  {meta['author']}")
        _log(f"  Jezik:  {meta['language']}")
        _log(f"  Tekst:  {len(text):,} znakova")
        if len(text) < 500:
            _log(f"  ⚠ Malo teksta ekstraktovano — EPUB možda ima nestandardnu strukturu", "yellow")
    except Exception as e:
        _log(f"✗ Greška pri parsiranju EPUB-a:", "red")
        # Prikaži svaki red greške zasebno za čitljivost
        for line in str(e).split("\n"):
            if line.strip():
                _log(f"  {line.strip()}", "red" if "zakazao" in line else "yellow")
        _log("\nSavjeti:", "cyan")
        _log("  • Provjeri da li je fajl otvoren u drugoj aplikaciji", "dim")
        _log("  • Pokušaj: unzip -t '" + epub_path + "' (provjera integriteta)", "dim")
        _log("  • Ako je fajl sa MoonReader-a, može imati DRM zaštitu", "dim")
        return

    _log("\n► Ekstrahujem vlastita imena (NER)...", "cyan")
    names = extract_names(text, verbose=verbose)

    if not names:
        _log("✗ Nisu pronađena vlastita imena.", "yellow")
        return

    _log(f"  Pronađeno: {len(names)} jedinstvenih entiteta")

    # Provjera AI ključeva
    available = [p for p in PROVIDER_ORDER if get_api_key(p, env_keys)]
    if not available:
        _log("\n✗ Nisu postavljeni API ključevi!", "red")
        _log("  Odaberi opciju 2 iz menija za postavljanje ključeva.", "yellow")
        return

    _log(f"\n► Fonetizacija via AI (dostupni: {', '.join(available)})...", "cyan")

    if RICH:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Fonetizacija...", total=len(names))
            processed = [0]

            # Pratimo progress kroz monkey-patching batch poziva
            phonetics = {}
            for i in range(0, len(names), batch):
                chunk = names[i:i+batch]
                result, provider = ai_phonetize_batch(chunk, env_keys, verbose=False)
                for name in chunk:
                    phonetics[name] = result.get(name, name).strip().strip('"')
                progress.advance(task, len(chunk))
                if i + batch < len(names):
                    time.sleep(0.8)
    else:
        phonetics = phonetize_all(names, env_keys, batch_size=batch, verbose=verbose)

    # Statistike
    changed = sum(1 for n, p in phonetics.items() if n != p)
    _log(f"\n  ✓ Fonetizacija završena: {len(phonetics)} entiteta")
    _log(f"  Promijenjenih: {changed} / {len(phonetics)}")

    # Preview
    _show_preview(names, phonetics)

    # Potvrda zapisa
    out_path = str(Path(epub_path).resolve()) + ".replacement"
    if RICH:
        save = Confirm.ask(f"[cyan]Snimi u: {out_path}?[/]", default=True)
    else:
        save_in = input(f"Snimi u {out_path}? [Y/n]: ").strip().lower()
        save = save_in != "n"

    if save:
        written = write_replacement_file(epub_path, phonetics, out_path)
        _log(f"\n✓ Zapisano: {written}", "green")
        _log(f"  Linija: {len(phonetics)}", "green")
    else:
        _log("Poništeno.", "yellow")


def _menu_api_keys(env_keys: dict) -> dict:
    """Podizbornik: pregled i uređivanje API ključeva."""
    if RICH:
        table = Table(title="API Ključevi", box=box.ROUNDED)
        table.add_column("Provider", style="cyan")
        table.add_column("Ključ", style="white")
        table.add_column("Status", style="dim")
        for provider in PROVIDER_ORDER:
            cfg  = AI_CONFIG[provider]
            key  = get_api_key(provider, env_keys)
            status = "[green]✓ postavljen[/]" if key else "[red]✗ nedostaje[/]"
            masked = (key[:6] + "..." + key[-4:]) if key and len(key) > 12 else "—"
            table.add_row(cfg["label"], masked, status)
        console.print(table)
    else:
        print("\n═══ API Ključevi ═══")
        for provider in PROVIDER_ORDER:
            key = get_api_key(provider, env_keys)
            status = "✓" if key else "✗"
            print(f"  {status} {AI_CONFIG[provider]['label']}")
        print()

    if RICH:
        edit = Confirm.ask("[cyan]Postavi/izmijeni ključeve?[/]", default=False)
    else:
        edit_in = input("Postavi/izmijeni ključeve? [y/N]: ").strip().lower()
        edit = edit_in == "y"

    if not edit:
        return env_keys

    # Prihvati ključeve interaktivno
    new_keys = dict(env_keys)
    for provider in PROVIDER_ORDER:
        cfg = AI_CONFIG[provider]
        env_var = cfg["env_key"]
        current = new_keys.get(env_var, "")
        masked = (current[:6] + "...") if current else "prazno"

        if RICH:
            val = Prompt.ask(
                f"[cyan]{cfg['label']}[/] ({env_var}) [{masked}]",
                default="",
                password=True
            ).strip()
        else:
            val = input(f"  {cfg['label']} [{masked}] (Enter za skip): ").strip()

        if val:
            new_keys[env_var] = val

    # Snimi u .env.names
    env_file = Path(ENV_FILE)
    lines = ["# BooklyTTS API ključevi\n"]
    for provider in PROVIDER_ORDER:
        cfg = AI_CONFIG[provider]
        env_var = cfg["env_key"]
        val = new_keys.get(env_var, "")
        if val:
            lines.append(f"{env_var}={val}\n")
        else:
            lines.append(f"# {env_var}=your_key_here\n")

    with open(env_file, "w") as f:
        f.writelines(lines)

    _log(f"✓ Ključevi snimljeni u {env_file}", "green")
    return new_keys


def _menu_test_ai(env_keys: dict):
    """Podizbornik: test AI konekcije — testira SVE providere."""
    test_names = ["John", "Shakespeare", "Paris", "Wolfgang", "Lejla", "Muhamed"]
    _log(f"\n► Test fonetizacije: {test_names}", "cyan")
    _log("  (testira sve dostupne providere, ne staje na prvom)\n", "dim")

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
        _log("\n  Ni jedan provider nije uspio!", "red")
        _log("  Provjeri:", "yellow")
        _log("    • API ključevi su tačni (opcija 2 u meniju)", "dim")
        _log("    • Internet konekcija radi", "dim")
        _log("    • Quota nije iscrpljena na providerima", "dim")
    else:
        _log("\n  Fallback lanac spreman za upotrebu.", "green")


def _menu_pregledaj():
    """Podizbornik: pregled .replacement fajla."""
    if RICH:
        path = Prompt.ask("[cyan]Putanja do .replacement fajla[/]").strip()
    else:
        path = input("Putanja do .replacement fajla: ").strip()

    path = path.strip("'\"")
    p = Path(path)

    if not p.exists():
        _log(f"✗ Fajl nije pronađen: {path}", "red")
        return

    with open(p, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]

    _log(f"\n► {p.name}  ({len(lines)} entiteta)\n", "cyan")

    if RICH:
        table = Table(box=box.SIMPLE, border_style="dim")
        table.add_column("#", style="dim", width=5)
        table.add_column("Originalno", style="white")
        table.add_column("Fonetizirano", style="green")
        for i, line in enumerate(lines[:50], 1):
            parts = line.split("#>#")
            if len(parts) == 2:
                orig, phon = parts
                color = "green" if orig.strip() != phon.strip() else "dim"
                table.add_row(str(i), orig.strip(), f"[{color}]{phon.strip()}[/]")
        console.print(table)
    else:
        for i, line in enumerate(lines[:50], 1):
            print(f"  {i:3}. {line}")

    if len(lines) > 50:
        _log(f"... i još {len(lines) - 50} redova", "dim")


# ════════════════════════════════════════════════════════════
# CLI — CLICK
# ════════════════════════════════════════════════════════════

@click.command()
@click.option("--epub", "-e", default=None,
              help="Putanja do EPUB fajla (izostavi za interaktivni meni)")
@click.option("--output", "-o", default=None,
              help="Putanja do .replacement output fajla")
@click.option("--batch", "-b", default=BATCH_SIZE, show_default=True,
              help="Broj imena po AI pozivu")
@click.option("--provider", "-p",
              type=click.Choice(PROVIDER_ORDER + ["auto"]),
              default="auto", show_default=True,
              help="AI provider (auto = fallback lanac)")
@click.option("--env-file", default=ENV_FILE, show_default=True,
              help="Putanja do .env fajla sa API ključevima")
@click.option("--verbose", "-v", is_flag=True,
              help="Detaljan ispis")
@click.option("--dry-run", is_flag=True,
              help="Samo ekstrahuji imena, bez AI fonetizacije")
def main(epub, output, batch, provider, env_file, verbose, dry_run):
    """
    EPUB Fonetizator — ekstrakcija vlastitih imena i AI fonetizacija.

    \b
    Primjeri:
      python3 epub_fonetizator.py                        # interaktivni meni
      python3 epub_fonetizator.py --epub knjiga.epub     # direktna obrada
      python3 epub_fonetizator.py --epub k.epub --dry-run
    """
    # Provjera zavisnosti
    if not _check_dependencies():
        sys.exit(1)

    if NLTK_OK:
        _check_nltk_data()

    # Učitaj API ključeve
    env_keys = load_env(env_file)

    # Bez argumenta → interaktivni meni
    if epub is None:
        interactive_menu(env_keys)
        return

    # Direktna obrada
    _print_banner()
    _log(f"► EPUB: {epub}", "cyan")

    # Provjera fajla
    if not Path(epub).exists():
        _log(f"✗ EPUB fajl nije pronađen: {epub}", "red")
        sys.exit(1)

    # Ekstrakcija teksta
    _log("► Ekstrahujem tekst...", "cyan")
    try:
        text, meta = extract_text_from_epub(epub)
        _log(f"  {meta['title']} — {meta['author']}")
        _log(f"  {len(text)} znakova")
    except Exception as e:
        _log(f"✗ EPUB parse greška: {e}", "red")
        sys.exit(1)

    # NER
    _log("► NER ekstrakcija...", "cyan")
    names = extract_names(text, verbose=verbose)
    _log(f"  Pronađeno: {len(names)} entiteta")

    if not names:
        _log("Nisu pronađena vlastita imena. Kraj.", "yellow")
        sys.exit(0)

    if dry_run:
        _log("\n─── DRY RUN — lista pronađenih imena ───", "yellow")
        for name in names:
            print(f"  {name}")
        _log(f"\nUkupno: {len(names)}", "green")
        sys.exit(0)

    # Provjera AI ključeva
    if provider == "auto":
        providers = PROVIDER_ORDER
    else:
        providers = [provider]

    available = [p for p in providers if get_api_key(p, env_keys)]
    if not available:
        _log("✗ Nema dostupnih API ključeva!", "red")
        _log(f"  Postavi ključeve u: {env_file}", "yellow")
        sys.exit(1)

    _log(f"► AI fonetizacija (provideri: {', '.join(available)})...", "cyan")
    phonetics = phonetize_all(names, env_keys, batch_size=batch, verbose=verbose)

    # Statistike
    changed = sum(1 for n, p in phonetics.items() if n != p)
    _log(f"\n✓ Fonetizacija završena", "green")
    _log(f"  Ukupno: {len(phonetics)} | Promijenjeno: {changed}", "green")

    # Preview
    if verbose:
        _show_preview(names, phonetics)

    # Zapis
    out = write_replacement_file(epub, phonetics, output)
    _log(f"✓ Output: {out}", "green")

    # Kratki sažetak promijenjenih
    changed_items = [(n, p) for n, p in phonetics.items() if n != p]
    if changed_items and verbose:
        _log("\nPromijenjeni entiteti:", "cyan")
        for orig, phon in changed_items[:20]:
            print(f"  {orig} → {phon}")
        if len(changed_items) > 20:
            print(f"  ... i još {len(changed_items) - 20}")


if __name__ == "__main__":
    main()
