#!/bin/bash
# bookly_tts_03_app.sh - BooklyTTS sa edge-tts (Microsoft Neural)
# Pokrenuti u Termux-u: bash bookly_tts_03_app.sh

set -e

PROJECT_DIR="$HOME/BooklyTTS"
cd "$PROJECT_DIR" || exit 1

# Aktivacija venv-a
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "================================================"
echo "  BooklyTTS - Kreiranje aplikacije (3/3)"
echo "  TTS: Microsoft Edge Neural (edge-tts)"
echo "================================================"
echo ""

# Kreiranje direktorija
mkdir -p app/templates app/static/css app/static/js app/static/audio/chunks
mkdir -p reference_audio uploads output library scripts tests
touch app/static/audio/chunks/.gitkeep uploads/.gitkeep output/.gitkeep library/.gitkeep

# --------------------------------------------------
echo "[1/8] Kreiranje .env konfiguracije..."
# --------------------------------------------------
cat > .env << 'EOF'
FLASK_APP=app
FLASK_ENV=development
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
TTS_ENGINE=edge-tts
DEFAULT_VOICE=hr-HR-GabrijelaNeural
DEFAULT_LANGUAGE=hr
OUTPUT_DIR=output
UPLOAD_DIR=uploads
EOF
echo "  .env kreiran"

# --------------------------------------------------
echo "[2/8] Kreiranje app/__init__.py..."
# --------------------------------------------------
cat > app/__init__.py << 'EOF'
"""BooklyTTS - EPUB to Audiobook sa Microsoft Edge Neural TTS"""
import os
from flask import Flask
from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24).hex()
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_DIR', 'uploads')
    app.config['OUTPUT_FOLDER'] = os.getenv('OUTPUT_DIR', 'output')
    
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
    
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    return app
EOF

# --------------------------------------------------
echo "[3/8] Kreiranje app/tts_engine.py..."
# --------------------------------------------------
cat > app/tts_engine.py << 'EOF'
"""TTS Engine wrapper za edge-tts (Microsoft Neural)"""
import os
import asyncio

class TTSEngine:
    """Microsoft Edge TTS - najbolji HR/BS glasovi bez modela"""
    
    VOICES = {
        'hr': {
            'female': 'hr-HR-GabrijelaNeural',
            'male': 'hr-HR-SreckoNeural'
        },
        'bs': {
            'male': 'bs-BA-GoranNeural',
            'female': 'bs-BA-VesnaNeural'
        },
        'sr': {
            'male': 'sr-RS-NicholasNeural',
            'female': 'sr-RS-SophieNeural'
        },
        'cs': {
            'male': 'cs-CZ-AntoninNeural',
            'female': 'cs-CZ-VlastaNeural'
        }
    }
    
    def __init__(self, voice='hr-HR-GabrijelaNeural'):
        self.voice = voice
        self.ready = True
    
    def is_ready(self):
        return self.ready
    
    def synthesize(self, text, output_path, voice=None):
        """Sinteza govora koristeci edge-tts"""
        if voice is None:
            voice = self.voice
        
        async def _synthesize():
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
        
        asyncio.run(_synthesize())
        return output_path
EOF

# --------------------------------------------------
echo "[4/8] Kreiranje app/epub_processor.py..."
# --------------------------------------------------
cat > app/epub_processor.py << 'EOF'
"""EPUB procesor za ekstrakciju teksta"""
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import re

class EPUBProcessor:
    def extract_metadata(self, epub_path):
        try:
            book = epub.read_epub(epub_path)
            metadata = {'title': 'Nepoznat naslov', 'author': 'Nepoznat autor', 'language': 'hr'}
            titles = book.get_metadata('DC', 'title')
            if titles: metadata['title'] = titles[0][0]
            creators = book.get_metadata('DC', 'creator')
            if creators: metadata['author'] = creators[0][0]
            return metadata
        except:
            return {'title': 'Greska', 'author': 'Greska', 'language': 'hr'}
    
    def extract_chapters(self, epub_path):
        book = epub.read_epub(epub_path)
        chapters = []
        chapter_index = 0
        
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            try:
                content = item.get_content()
                soup = BeautifulSoup(content, 'html.parser')
                for script in soup(["script", "style"]): script.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                if len(text) < 100: continue
                
                title = f"Poglavlje {chapter_index + 1}"
                for h_tag in ['h1', 'h2', 'h3']:
                    header = soup.find(h_tag)
                    if header:
                        title = header.get_text(strip=True)
                        break
                
                chapters.append({'id': chapter_index, 'title': title, 'text': text, 'char_count': len(text)})
                chapter_index += 1
            except: continue
        
        return chapters if chapters else [{'id': 0, 'title': 'Kompletan tekst', 'text': 'Nema teksta', 'char_count': 0}]
EOF

# --------------------------------------------------
echo "[5/8] Kreiranje app/audio_builder.py..."
# --------------------------------------------------
cat > app/audio_builder.py << 'EOF'
"""Audio builder za spajanje chunkova"""
import os
from pydub import AudioSegment

class AudioBuilder:
    def __init__(self, output_dir): self.output_dir = output_dir
    
    def concatenate(self, audio_files, output_path, crossfade_ms=50, add_silence_ms=500):
        if not audio_files: raise ValueError("Nema audio fajlova")
        combined = AudioSegment.from_file(audio_files[0])
        silence = AudioSegment.silent(duration=add_silence_ms)
        for audio_file in audio_files[1:]:
            combined = combined.append(silence, crossfade=0)
            combined = combined.append(AudioSegment.from_file(audio_file), crossfade=crossfade_ms)
        combined.export(output_path, format="mp3", bitrate="192k")
        return output_path
EOF

# --------------------------------------------------
echo "[6/8] Kreiranje app/routes.py..."
# --------------------------------------------------
cat > app/routes.py << 'EOF'
"""Flask rute za BooklyTTS"""
import os, uuid
from flask import Blueprint, render_template, request, jsonify, send_file, current_app
from werkzeug.utils import secure_filename
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor
from app.audio_builder import AudioBuilder

main_bp = Blueprint('main', __name__)
tts_engine = TTSEngine()
epub_processor = EPUBProcessor()
audio_builder = AudioBuilder(output_dir='output')

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/upload-epub', methods=['POST'])
def upload_epub():
    if 'epub_file' not in request.files: return jsonify({'error': 'Nema fajla'}), 400
    file = request.files['epub_file']
    if not file.filename.endswith('.epub'): return jsonify({'error': 'Mora biti .epub'}), 400
    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    metadata = epub_processor.extract_metadata(filepath)
    chapters = epub_processor.extract_chapters(filepath)
    return jsonify({'success': True, 'filename': filename, 'metadata': metadata, 'chapter_count': len(chapters)})

@main_bp.route('/voices')
def list_voices():
    return jsonify(TTSEngine.VOICES)

@main_bp.route('/start-conversion', methods=['POST'])
def start_conversion():
    data = request.get_json()
    epub_filename = data.get('epub_filename')
    voice = data.get('voice', 'hr-HR-GabrijelaNeural')
    
    if not epub_filename: return jsonify({'error': 'Nedostaje EPUB'}), 400
    
    epub_path = os.path.join(current_app.config['UPLOAD_FOLDER'], epub_filename)
    if not os.path.exists(epub_path): return jsonify({'error': 'EPUB ne postoji'}), 404
    
    job_id = uuid.uuid4().hex[:12]
    chapters = epub_processor.extract_chapters(epub_path)
    
    audio_files = []
    for i, chapter in enumerate(chapters):
        if len(chapter['text'].strip()) < 50: continue
        chunk_filename = f"{job_id}_ch{i:04d}.mp3"
        chunk_path = os.path.join(current_app.config['OUTPUT_FOLDER'], chunk_filename)
        tts_engine.synthesize(chapter['text'], chunk_path, voice=voice)
        audio_files.append(chunk_path)
    
    output_filename = f"audiobook_{job_id}.mp3"
    output_path = os.path.join(current_app.config['OUTPUT_FOLDER'], output_filename)
    audio_builder.concatenate(audio_files, output_path)
    
    for chunk in audio_files:
        try: os.remove(chunk)
        except OSError: pass
    
    return jsonify({'success': True, 'output_filename': output_filename, 'message': f'Zavrseno! {len(audio_files)} poglavlja.'})

@main_bp.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(current_app.config['OUTPUT_FOLDER'], secure_filename(filename))
    if not os.path.exists(filepath): return jsonify({'error': 'Fajl ne postoji'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)

@main_bp.route('/status')
def status():
    return jsonify({'tts_ready': tts_engine.is_ready(), 'engine': 'Microsoft Edge Neural', 'default_voice': 'hr-HR-GabrijelaNeural'})
EOF

# --------------------------------------------------
echo "[7/8] Kreiranje HTML template-a..."
# --------------------------------------------------
cat > app/templates/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="hr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BooklyTTS - EPUB u Audiobook</title>
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>📚 BooklyTTS</h1>
            <p class="subtitle">EPUB → Audiobook sa Microsoft Neural glasovima</p>
            <p class="lang-info">🎯 HR/BS/SR glasovi: Gabrijela, Srecko, Goran, Vesna</p>
        </header>
        <main>
            <section class="card status-section">
                <h2>📊 Status</h2>
                <div id="status-indicator">
                    <span class="status-dot ready"></span>
                    <span id="status-text">Spreman - Microsoft Edge TTS</span>
                </div>
            </section>
            <section class="card">
                <h2>🎤 Odaberi glas</h2>
                <select id="voice-select">
                    <optgroup label="Hrvatski">
                        <option value="hr-HR-GabrijelaNeural" selected>Gabrijela (zenski)</option>
                        <option value="hr-HR-SreckoNeural">Srecko (muski)</option>
                    </optgroup>
                    <optgroup label="Bosanski">
                        <option value="bs-BA-VesnaNeural">Vesna (zenski)</option>
                        <option value="bs-BA-GoranNeural">Goran (muski)</option>
                    </optgroup>
                    <optgroup label="Srpski">
                        <option value="sr-RS-SophieNeural">Sophie (zenski)</option>
                        <option value="sr-RS-NicholasNeural">Nicholas (muski)</option>
                    </optgroup>
                    <optgroup label="Ceski">
                        <option value="cs-CZ-VlastaNeural">Vlasta (zenski)</option>
                        <option value="cs-CZ-AntoninNeural">Antonin (muski)</option>
                    </optgroup>
                </select>
            </section>
            <section class="card">
                <h2>📖 EPUB fajl</h2>
                <form id="epub-form" enctype="multipart/form-data">
                    <input type="file" name="epub_file" accept=".epub" id="epub-file">
                    <button type="submit" class="btn btn-primary">Upload EPUB</button>
                </form>
                <div id="epub-info" style="display:none;">
                    <p><strong>Naslov:</strong> <span id="epub-title"></span></p>
                    <p><strong>Autor:</strong> <span id="epub-author"></span></p>
                    <p><strong>Poglavlja:</strong> <span id="epub-chapters"></span></p>
                </div>
            </section>
            <section class="card">
                <h2>▶️ Konverzija</h2>
                <button id="start-conversion" class="btn btn-success btn-large">🎧 Pokreni konverziju</button>
                <div id="progress" style="display:none;">
                    <p id="progress-text">⏳ Konverzija u toku...</p>
                </div>
            </section>
            <section class="card">
                <h2>📁 Audiobookovi</h2>
                <ul id="output-list"><li class="empty">Uploaduj EPUB za konverziju</li></ul>
            </section>
        </main>
        <footer>
            <p>BooklyTTS · Microsoft Edge Neural TTS · HR/BS/SR · <a href="https://github.com">GitHub</a></p>
        </footer>
    </div>
    <script src="/static/js/app.js"></script>
</body>
</html>
HTMLEOF

# --------------------------------------------------
echo "[8/8] Kreiranje CSS i JS..."
# --------------------------------------------------
cat > app/static/css/style.css << 'CSSEOF'
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #1a1a2e; color: #e0e0e0; min-height: 100vh; }
.container { max-width: 700px; margin: 0 auto; padding: 20px; }
header { text-align: center; padding: 30px 20px 20px; }
header h1 { font-size: 2.2em; color: #7b68ee; }
.subtitle { color: #aaa; margin-top: 8px; }
.lang-info { font-size: 0.85em; color: #4ecdc4; margin-top: 8px; padding: 8px; background: rgba(78,205,196,0.1); border-radius: 8px; }
.card { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 24px; margin: 16px 0; }
.card h2 { color: #7b68ee; margin-bottom: 16px; }
.btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-size: 0.95em; }
.btn-primary { background: #7b68ee; color: white; }
.btn-success { background: linear-gradient(135deg, #11998e, #38ef7d); color: white; }
.btn-large { width: 100%; padding: 16px; font-size: 1.1em; margin-top: 12px; }
input[type="file"], select { margin: 8px 0; padding: 8px; background: rgba(255,255,255,0.1); color: white; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; width: 100%; }
.status-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }
.status-dot.ready { background: #38ef7d; }
ul { list-style: none; }
li { padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
li.empty { color: #666; font-style: italic; }
footer { text-align: center; padding: 40px 20px; color: #666; font-size: 0.85em; }
footer a { color: #7b68ee; }
CSSEOF

cat > app/static/js/app.js << 'JSEOF'
let uploadedEpub = null;
document.getElementById('epub-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
        const response = await fetch('/upload-epub', { method: 'POST', body: formData });
        const data = await response.json();
        if (data.success) {
            uploadedEpub = data.filename;
            document.getElementById('epub-info').style.display = 'block';
            document.getElementById('epub-title').textContent = data.metadata.title;
            document.getElementById('epub-author').textContent = data.metadata.author;
            document.getElementById('epub-chapters').textContent = data.chapter_count;
            alert('EPUB uploadovan! ' + data.chapter_count + ' poglavlja.');
        } else { alert(data.error); }
    } catch (err) { alert('Greska: ' + err.message); }
});

document.getElementById('start-conversion').addEventListener('click', async () => {
    if (!uploadedEpub) { alert('Prvo uploaduj EPUB!'); return; }
    const voice = document.getElementById('voice-select').value;
    document.getElementById('progress').style.display = 'block';
    document.getElementById('start-conversion').disabled = true;
    document.getElementById('progress-text').textContent = '⏳ Konverzija u toku...';
    try {
        const response = await fetch('/start-conversion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ epub_filename: uploadedEpub, voice: voice })
        });
        const data = await response.json();
        if (data.success) {
            document.getElementById('progress-text').textContent = '✅ ' + data.message;
            setTimeout(() => location.reload(), 2000);
        } else {
            document.getElementById('progress-text').textContent = '❌ ' + data.error;
            document.getElementById('start-conversion').disabled = false;
        }
    } catch (err) {
        document.getElementById('progress-text').textContent = '❌ Greska: ' + err.message;
        document.getElementById('start-conversion').disabled = false;
    }
});
JSEOF

# Kreiranje run skripti
cat > run_web.sh << 'EOF'
#!/bin/bash
source .venv/bin/activate
export FLASK_APP=app
echo "🌐 BooklyTTS Web UI"
echo "   http://localhost:5000"
python3 -m flask run --host=0.0.0.0 --port=5000
EOF
chmod +x run_web.sh

# CLI
cat > app/cli.py << 'EOF'
#!/usr/bin/env python3
"""BooklyTTS CLI"""
import os, sys, asyncio, click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

console = Console()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor
from app.audio_builder import AudioBuilder

engine = TTSEngine()
epub = EPUBProcessor()
builder = AudioBuilder(output_dir='output')

@click.command()
@click.option('--epub', help='EPUB fajl')
@click.option('--voice', default='hr-HR-GabrijelaNeural', help='Glas')
@click.option('--output', help='Izlazni fajl')
def cli(epub, voice, output):
    """BooklyTTS - EPUB u Audiobook"""
    if not epub:
        console.print("[red]Navedi --epub[/red]")
        return
    
    console.print(f"[cyan]BooklyTTS - Konverzija[/cyan]")
    chapters = epub.extract_chapters(epub)
    console.print(f"[green]{len(chapters)} poglavlja[/green]")
    
    audio_files = []
    for i, ch in enumerate(chapters):
        if len(ch['text'].strip()) < 50: continue
        out = f"output/ch_{i:04d}.mp3"
        console.print(f"  [{i+1}/{len(chapters)}] {ch['title'][:40]}...")
        engine.synthesize(ch['text'], out, voice=voice)
        audio_files.append(out)
    
    output_path = output or f"audiobook_{os.path.basename(epub).replace('.epub','')}.mp3"
    builder.concatenate(audio_files, output_path)
    console.print(f"[green bold]✅ {output_path}[/green bold]")
    
    for f in audio_files:
        try: os.remove(f)
        except: pass

if __name__ == '__main__':
    cli()
EOF
chmod +x app/cli.py

cat > run_cli.sh << 'EOF'
#!/bin/bash
source .venv/bin/activate
python3 -m app.cli "$@"
EOF
chmod +x run_cli.sh

echo ""
echo "================================================"
echo "  BOOKLYTTS KOMPLETNO KREIRAN! (3/3)"
echo "================================================"
echo ""
echo "  🚀 POKRETANJE:"
echo ""
echo "  Web UI:"
echo "    bash run_web.sh"
echo "    → http://localhost:5000"
echo ""
echo "  CLI:"
echo "    bash run_cli.sh --epub tvoja_knjiga.epub --voice hr-HR-GabrijelaNeural"
echo ""
echo "  🎤 HR/BS GLASOVI:"
echo "    hr-HR-GabrijelaNeural (zenski HR)"
echo "    hr-HR-SreckoNeural (muski HR)"
echo "    bs-BA-VesnaNeural (zenski BS)"
echo "    bs-BA-GoranNeural (muski BS)"
echo ""
echo "  💡 Testiraj:"
echo "    edge-tts --text 'Dobar dan' -v hr-HR-GabrijelaNeural --write-media test.mp3"
echo ""
