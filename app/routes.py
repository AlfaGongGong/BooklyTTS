# routes.py — BooklyTTS
# Fixes: BUG-01 (convert.html ne postoji → redirect),
#        BUG-02 (/start-conversion, /conversion-progress/<job_id>),
#        BUG-03 (/profiles, /replacements CRUD),
#        BUG-05 (secure_filename na uploadu)

import os
import uuid
import json
import threading
import time
import queue
from flask import (Blueprint, render_template, request, jsonify,
                   send_file, Response, abort, redirect, url_for)
from werkzeug.utils import secure_filename
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor
from app.audio_builder import AudioBuilder
from app.replacer import NameReplacer

main_bp = Blueprint('main', __name__)
jobs = {}

# --- helpers ---

def is_valid_epub(filepath):
    import zipfile
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            return ('mimetype' in zf.namelist() or
                    'META-INF/container.xml' in zf.namelist())
    except Exception:
        return False


# --- page routes ---

@main_bp.route('/')
def index():
    return render_template('index.html')


@main_bp.route('/reader')
def reader_page():
    return render_template('reader.html')


# BUG-01 FIX: /convert ne može renderirati convert.html koji ne postoji.
# Preusmjeravamo na /reader koji je funkcionalan konverter + čitač.
@main_bp.route('/convert')
def convert_page():
    return redirect(url_for('main.reader_page'))


@main_bp.route('/rules')
def rules_page():
    return render_template('rules.html')


@main_bp.route('/status')
def status():
    import shutil
    return jsonify({
        'tts_ready': True,
        'disk_free_mb': shutil.disk_usage('.').free // (1024 * 1024)
    })


# --- upload ---

@main_bp.route('/upload-epub', methods=['POST'])
def upload_epub():
    if 'epub_file' not in request.files:
        return jsonify({'error': 'Nema fajla'}), 400
    file = request.files['epub_file']
    if not file.filename.endswith('.epub'):
        return jsonify({'error': 'Mora .epub'}), 400
    # BUG-05 FIX: sanitizuj filename
    safe_name = secure_filename(file.filename)
    filename = f"{uuid.uuid4().hex}_{safe_name}"
    filepath = os.path.join('uploads', filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(filepath)
    if not is_valid_epub(filepath):
        os.remove(filepath)
        return jsonify({'error': 'Nevalidan EPUB'}), 400
    epub_proc = EPUBProcessor()
    try:
        metadata = epub_proc.extract_metadata(filepath)
        chapters = epub_proc.extract_chapters(filepath)
        return jsonify({
            'success': True,
            'filename': filename,
            'metadata': metadata,
            'chapter_count': len(chapters),
            'chapters': [
                {'id': c['id'], 'title': c['title'],
                 'char_count': c['char_count']}
                for c in chapters
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# --- voice test / download / list ---

@main_bp.route('/test-voice', methods=['POST'])
def test_voice():
    data = request.get_json()
    tts = TTSEngine()
    tmp = tts.stream_chapter(
        'Dobar dan.',
        voice=data.get('voice', 'hr-HR-GabrijelaNeural'),
        max_chars=300
    )
    return send_file(tmp, mimetype='audio/mpeg')


@main_bp.route('/download/<filename>')
def download_file(filename):
    output_dir = os.path.abspath('output')
    filepath = os.path.abspath(
        os.path.join(output_dir, secure_filename(filename)))
    if not filepath.startswith(output_dir):
        abort(403)
    if not os.path.exists(filepath):
        return jsonify({'error': 'Fajl ne postoji'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)


@main_bp.route('/list-audiobooks')
def list_audiobooks():
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    files = [f for f in os.listdir(output_dir) if f.endswith('.mp3')]
    result = []
    for f in sorted(files,
                    key=lambda x: os.path.getmtime(
                        os.path.join(output_dir, x)),
                    reverse=True):
        path = os.path.join(output_dir, f)
        result.append({
            'name': f,
            'size_mb': round(os.path.getsize(path) / (1024 * 1024), 1),
            'date': time.strftime(
                '%d.%m.%Y %H:%M',
                time.localtime(os.path.getmtime(path)))
        })
    return jsonify(result[:20])


# -----------------------------------------------------------------------
# BUG-02 FIX: /start-conversion + /conversion-progress/<job_id>
# app.js šalje POST /start-conversion i otvara EventSource na
# /conversion-progress/<job_id> koji šalje SSE progres.
# -----------------------------------------------------------------------

_conv_jobs = {}   # job_id -> {'q': Queue, 'created': float}


def _cleanup_conv_jobs():
    """Ukloni job-ove starije od 10 minuta."""
    cutoff = time.time() - 600
    dead = [k for k, v in list(_conv_jobs.items())
            if v.get('created', 0) < cutoff]
    for k in dead:
        _conv_jobs.pop(k, None)


@main_bp.route('/start-conversion', methods=['POST'])
def start_conversion():
    _cleanup_conv_jobs()
    data = request.get_json() or {}
    epub_filename = data.get('epub_filename', '')
    voice = data.get('voice', 'hr-HR-GabrijelaNeural')
    chapter_ids = data.get('chapter_ids', None)   # None = sva poglavlja

    epub_path = None
    if epub_filename:
        candidate = os.path.join('uploads', secure_filename(epub_filename))
        if os.path.exists(candidate):
            epub_path = candidate

    if not epub_path:
        return jsonify({'error': 'EPUB nije pronađen'}), 404

    job_id = uuid.uuid4().hex[:12]
    q = queue.Queue()
    _conv_jobs[job_id] = {'q': q, 'created': time.time()}

    def run():
        try:
            epub_proc = EPUBProcessor()
            chapters = epub_proc.extract_chapters(epub_path)
            if chapter_ids:
                id_set = set(chapter_ids)
                chapters = [c for c in chapters if c['id'] in id_set]

            total = len(chapters)
            q.put({'progress': 0, 'status': f'Počinjemo ({total} pogl.)'})

            tts = TTSEngine()
            builder = AudioBuilder()
            parts = []

            for idx, ch in enumerate(chapters):
                q.put({
                    'progress': int(idx / total * 90),
                    'status': f'Poglavlje {idx+1}/{total}: {ch["title"]}'
                })
                import tempfile
                tmp = tempfile.NamedTemporaryFile(
                    suffix='.mp3', delete=False)
                tts.synthesize(ch['text'], tmp.name, voice)
                parts.append(tmp.name)

            q.put({'progress': 90, 'status': 'Spajam audio...'})
            os.makedirs('output', exist_ok=True)
            out_name = (secure_filename(
                os.path.basename(epub_path).replace('.epub', ''))
                + f'_{voice[:5]}.mp3')
            out_path = os.path.join('output', out_name)
            builder.concatenate(parts, out_path)
            for p in parts:
                try:
                    os.remove(p)
                except Exception:
                    pass

            q.put({'progress': 100, 'status': 'Gotovo!',
                   'output': out_name})
        except Exception as e:
            q.put({'progress': -1, 'status': f'Greška: {e}'})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({'job_id': job_id})


@main_bp.route('/conversion-progress/<job_id>')
def conversion_progress(job_id):
    if job_id not in _conv_jobs:
        def err_stream():
            yield 'data: {"error":"Job nije pronađen"}\n\n'
        return Response(err_stream(), mimetype='text/event-stream')

    q = _conv_jobs[job_id]['q']

    def generate():
        while True:
            try:
                msg = q.get(timeout=60)
                yield f'data: {json.dumps(msg)}\n\n'
                if msg.get('progress', 0) in (100, -1):
                    _conv_jobs.pop(job_id, None)
                    break
            except queue.Empty:
                yield 'data: {"progress":-1,"status":"Timeout"}\n\n'
                _conv_jobs.pop(job_id, None)
                break

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache',
                             'X-Accel-Buffering': 'no'})


# -----------------------------------------------------------------------
# BUG-03 FIX: /profiles + /replacements CRUD (rules.html endpoints)
# -----------------------------------------------------------------------

@main_bp.route('/profiles')
def get_profiles():
    replacer = NameReplacer()
    return jsonify(replacer.list_profiles())


@main_bp.route('/replacements', methods=['GET', 'POST'])
def replacements():
    replacer = NameReplacer()
    epub_name = request.args.get('epub') or (
        request.get_json() or {}).get('epub')

    if request.method == 'GET':
        return jsonify(replacer.get_rules(epub_name))

    # POST — dodaj pravilo
    data = request.get_json() or {}
    original = data.get('original', '').strip()
    replacement = data.get('replacement', '').strip()
    epub_name = data.get('epub')
    if not original:
        return jsonify({'error': 'original je obavezan'}), 400
    rules = replacer.add_rule(original, replacement, epub_name)
    return jsonify({'success': True, 'rules': rules})


@main_bp.route('/replacements/<path:original>', methods=['DELETE'])
def delete_replacement(original):
    from urllib.parse import unquote
    original = unquote(original)
    epub_name = request.args.get('epub')
    replacer = NameReplacer()
    rules = replacer.remove_rule(original, epub_name)
    return jsonify({'success': True, 'rules': rules})


@main_bp.route('/replacements/import', methods=['POST'])
def import_replacements():
    data = request.get_json() or {}
    text = data.get('text', '')
    epub_name = data.get('epub')
    replacer = NameReplacer()
    result = replacer.import_moonreader(text, epub_name)
    return jsonify(result)


@main_bp.route('/replacements/export')
def export_replacements():
    epub_name = request.args.get('epub')
    replacer = NameReplacer()
    text = replacer.export_moonreader(epub_name)
    return Response(text, mimetype='text/plain',
                    headers={'Content-Disposition':
                             'attachment; filename=replacements.txt'})


@main_bp.route('/replacements/merge-global', methods=['POST'])
def merge_global():
    data = request.get_json() or {}
    epub_name = data.get('epub')
    if not epub_name:
        return jsonify({'error': 'epub parametar je obavezan'}), 400
    replacer = NameReplacer()
    rules = replacer.merge_global_to_book(epub_name)
    return jsonify({'success': True, 'rules': rules})
