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
