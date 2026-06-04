import os, uuid, json, threading, time
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, Response
from werkzeug.utils import secure_filename
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor
from app.audio_builder import AudioBuilder

main_bp = Blueprint('main', __name__)
jobs = {}  # job_id -> {status, progress, result}

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/status')
def status():
    import shutil
    disk = shutil.disk_usage('.').free // (1024*1024)
    return jsonify({
        'tts_ready': True,
        'engine': 'edge-tts (Microsoft)',
        'disk_free_mb': disk
    })

@main_bp.route('/upload-epub', methods=['POST'])
def upload_epub():
    if 'epub_file' not in request.files:
        return jsonify({'error': 'Nema fajla'}), 400
    file = request.files['epub_file']
    if not file.filename.endswith('.epub'):
        return jsonify({'error': 'Mora biti .epub'}), 400
    
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join('uploads', filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(filepath)
    
    epub_proc = EPUBProcessor()
    try:
        metadata = epub_proc.extract_metadata(filepath)
        chapters = epub_proc.extract_chapters(filepath)
        return jsonify({
            'success': True, 'filename': filename,
            'metadata': metadata, 'chapter_count': len(chapters),
            'chapters': [{'id': c['id'], 'title': c['title'], 'char_count': c['char_count']} for c in chapters]
        })
    except Exception as e:
        return jsonify({'error': f'Greška: {str(e)}'}), 500

@main_bp.route('/start-conversion', methods=['POST'])
def start_conversion():
    data = request.get_json()
    epub_filename = data.get('epub_filename')
    voice = data.get('voice', 'hr-HR-GabrijelaNeural')
    chapter_ids = data.get('chapters', [])  # odabrana poglavlja
    
    if not epub_filename:
        return jsonify({'error': 'Nedostaje EPUB'}), 400
    
    epub_path = os.path.join('uploads', epub_filename)
    if not os.path.exists(epub_path):
        return jsonify({'error': 'EPUB ne postoji'}), 404
    
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {'status': 'starting', 'progress': 0, 'total': 0}
    
    def convert():
        try:
            epub_proc = EPUBProcessor()
            all_chapters = epub_proc.extract_chapters(epub_path)
            
            # Filtriraj odabrana poglavlja
            if chapter_ids:
                chapters = [c for c in all_chapters if c['id'] in chapter_ids]
            else:
                chapters = all_chapters
            
            jobs[job_id]['total'] = len(chapters)
            tts = TTSEngine()
            audio_files = []
            
            for i, chapter in enumerate(chapters):
                if len(chapter['text'].strip()) < 50: continue
                
                jobs[job_id]['status'] = f'Poglavlje {i+1}/{len(chapters)}'
                jobs[job_id]['progress'] = int((i / len(chapters)) * 100)
                
                chunk_filename = f"{job_id}_ch{i:04d}.mp3"
                chunk_path = os.path.join('output', chunk_filename)
                os.makedirs('output', exist_ok=True)
                
                tts.synthesize(chapter['text'], chunk_path, voice=voice)
                audio_files.append(chunk_path)
            
            jobs[job_id]['status'] = 'Spajanje...'
            jobs[job_id]['progress'] = 95
            
            output_filename = f"audiobook_{job_id}.mp3"
            output_path = os.path.join('output', output_filename)
            builder = AudioBuilder(output_dir='output')
            builder.concatenate(audio_files, output_path)
            
            for chunk in audio_files:
                try: os.remove(chunk)
                except: pass
            
            jobs[job_id]['status'] = 'Zavrseno'
            jobs[job_id]['progress'] = 100
            jobs[job_id]['result'] = output_filename
            
        except Exception as e:
            jobs[job_id]['status'] = f'Greska: {str(e)}'
    
    threading.Thread(target=convert, daemon=True).start()
    return jsonify({'job_id': job_id})

@main_bp.route('/conversion-progress/<job_id>')
def conversion_progress(job_id):
    def generate():
        while True:
            job = jobs.get(job_id, {})
            yield f"data: {json.dumps(job)}\n\n"
            if job.get('status') in ['Zavrseno', None] or 'Greska' in job.get('status', ''):
                break
            time.sleep(1)
    return Response(generate(), mimetype='text/event-stream')

@main_bp.route('/list-audiobooks')
def list_audiobooks():
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    files = [f for f in os.listdir(output_dir) if f.endswith('.mp3')]
    result = []
    for f in sorted(files, key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True):
        path = os.path.join(output_dir, f)
        result.append({
            'name': f,
            'size_mb': round(os.path.getsize(path) / (1024*1024), 1),
            'date': time.strftime('%d.%m.%Y %H:%M', time.localtime(os.path.getmtime(path)))
        })
    return jsonify(result[:20])

@main_bp.route('/test-voice', methods=['POST'])
def test_voice():
    data = request.get_json()
    voice = data.get('voice', 'hr-HR-GabrijelaNeural')
    sample_text = data.get('text', 'Dobar dan, ovo je test glasa.')
    
    tts = TTSEngine()
    tmp = tts.stream_chapter(sample_text, voice=voice, max_chars=500)
    return send_file(tmp, mimetype='audio/mpeg')

@main_bp.route('/download/<filename>')
def download_file(filename):
    output_dir = os.path.abspath('output')
    filepath = os.path.abspath(os.path.join(output_dir, secure_filename(filename)))
    if not filepath.startswith(output_dir):
        return jsonify({'error': 'Nedozvoljena putanja'}), 403
    if not os.path.exists(filepath):
        return jsonify({'error': 'Fajl ne postoji'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)
