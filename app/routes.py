import os, uuid, json, threading, time
from flask import Blueprint, render_template, request, jsonify, send_file, Response, abort
from werkzeug.utils import secure_filename
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor
from app.audio_builder import AudioBuilder

main_bp = Blueprint('main', __name__)
jobs = {}

def is_valid_epub(filepath):
    import zipfile
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            return 'mimetype' in zf.namelist() or 'META-INF/container.xml' in zf.namelist()
    except Exception: return False

@main_bp.route('/')
def index(): return render_template('index.html')

@main_bp.route('/reader')
def reader_page(): return render_template('reader.html')

@main_bp.route('/convert')
def convert_page(): return render_template('convert.html')

@main_bp.route('/rules')
def rules_page(): return render_template('rules.html')

@main_bp.route('/status')
def status():
    import shutil
    return jsonify({'tts_ready': True, 'disk_free_mb': shutil.disk_usage('.').free // (1024*1024)})

@main_bp.route('/upload-epub', methods=['POST'])
def upload_epub():
    if 'epub_file' not in request.files: return jsonify({'error': 'Nema fajla'}), 400
    file = request.files['epub_file']
    if not file.filename.endswith('.epub'): return jsonify({'error': 'Mora .epub'}), 400
    filename = f"{uuid.uuid4().hex}_{file.filename}"
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
        return jsonify({'success': True, 'filename': filename, 'metadata': metadata, 'chapter_count': len(chapters),
                       'chapters': [{'id': c['id'], 'title': c['title'], 'char_count': c['char_count'], 'text': c['text']} for c in chapters]})
    except Exception as e: return jsonify({'error': str(e)}), 500

@main_bp.route('/test-voice', methods=['POST'])
def test_voice():
    data = request.get_json()
    tts = TTSEngine()
    tmp = tts.stream_chapter('Dobar dan.', voice=data.get('voice', 'hr-HR-GabrijelaNeural'), max_chars=300)
    return send_file(tmp, mimetype='audio/mpeg')

@main_bp.route('/download/<filename>')
def download_file(filename):
    output_dir = os.path.abspath('output')
    filepath = os.path.abspath(os.path.join(output_dir, secure_filename(filename)))
    if not filepath.startswith(output_dir): abort(403)
    if not os.path.exists(filepath): return jsonify({'error': 'Fajl ne postoji'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)

@main_bp.route('/list-audiobooks')
def list_audiobooks():
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    files = [f for f in os.listdir(output_dir) if f.endswith('.mp3')]
    result = []
    for f in sorted(files, key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True):
        path = os.path.join(output_dir, f)
        result.append({'name': f, 'size_mb': round(os.path.getsize(path)/(1024*1024), 1),
                      'date': time.strftime('%d.%m.%Y %H:%M', time.localtime(os.path.getmtime(path)))})
    return jsonify(result[:20])
