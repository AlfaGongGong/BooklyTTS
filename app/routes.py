import os, uuid, json, threading, time, tempfile
from flask import Blueprint, render_template, request, jsonify, send_file, current_app, Response, abort
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
            names = zf.namelist()
            return 'mimetype' in names or 'META-INF/container.xml' in names
    except: return False

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/status')
def status():
    import shutil
    disk = shutil.disk_usage('.').free // (1024*1024)
    return jsonify({'tts_ready': True, 'engine': 'edge-tts', 'disk_free_mb': disk})

@main_bp.route('/upload-epub', methods=['POST'])
def upload_epub():
    if 'epub_file' not in request.files: return jsonify({'error':'Nema fajla'}), 400
    file = request.files['epub_file']
    if not file.filename.endswith('.epub'): return jsonify({'error':'Mora .epub'}), 400
    
    filename = f"{uuid.uuid4().hex}_{file.filename}"
    filepath = os.path.join('uploads', filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(filepath)
    
    if not is_valid_epub(filepath):
        os.remove(filepath)
        return jsonify({'error':'Nevalidan EPUB'}), 400
    
    epub_proc = EPUBProcessor()
    try:
        metadata = epub_proc.extract_metadata(filepath)
        chapters = epub_proc.extract_chapters(filepath)
        return jsonify({'success':True, 'filename':filename, 'metadata':metadata, 'chapter_count':len(chapters),
                       'chapters':[{'id':c['id'],'title':c['title'],'char_count':c['char_count']} for c in chapters]})
    except Exception as e:
        return jsonify({'error':str(e)}), 500

@main_bp.route('/start-conversion', methods=['POST'])
def start_conversion():
    data = request.get_json()
    epub_filename = data.get('epub_filename')
    voice = data.get('voice','hr-HR-GabrijelaNeural')
    chapter_ids = data.get('chapters',[])
    
    if not epub_filename: return jsonify({'error':'Nedostaje EPUB'}), 400
    epub_path = os.path.join('uploads', epub_filename)
    if not os.path.exists(epub_path): return jsonify({'error':'EPUB ne postoji'}), 404
    
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {'status':'starting','progress':0,'total':0}
    
    def convert():
        try:
            epub_proc = EPUBProcessor()
            all_chapters = epub_proc.extract_chapters(epub_path)
            chapters = [c for c in all_chapters if c['id'] in chapter_ids] if chapter_ids else all_chapters
            
            jobs[job_id]['total'] = len(chapters)
            tts = TTSEngine()
            audio_files = []
            
            for i, chapter in enumerate(chapters):
                if len(chapter['text'].strip()) < 50: continue
                jobs[job_id]['status'] = f'Poglavlje {i+1}/{len(chapters)}'
                jobs[job_id]['progress'] = int((i/len(chapters))*100)
                
                chunk_path = os.path.join('output', f"{job_id}_ch{i:04d}.mp3")
                os.makedirs('output', exist_ok=True)
                tts.synthesize(chapter['text'], chunk_path, voice=voice)
                audio_files.append(chunk_path)
            
            jobs[job_id]['status'] = 'Spajanje...'
            jobs[job_id]['progress'] = 95
            
            output_filename = f"audiobook_{job_id}.mp3"
            output_path = os.path.join('output', output_filename)
            AudioBuilder().concatenate(audio_files, output_path)
            
            for chunk in audio_files:
                try: os.remove(chunk)
                except: pass
            
            # B-09: Snimi u historiju
            from app.database import save_conversion
            save_conversion(epub_filename, voice, len(chapters), output_filename)
            
            jobs[job_id]['status'] = 'Zavrseno'
            jobs[job_id]['progress'] = 100
            jobs[job_id]['result'] = output_filename
            
            # O-05: Očisti job nakon 5 minuta
            def cleanup():
                time.sleep(300)
                jobs.pop(job_id, None)
            threading.Thread(target=cleanup, daemon=True).start()
            
        except Exception as e:
            jobs[job_id]['status'] = f'Greska: {str(e)}'
    
    threading.Thread(target=convert, daemon=True).start()
    return jsonify({'job_id': job_id})

@main_bp.route('/conversion-progress/<job_id>')
def conversion_progress(job_id):
    if job_id not in jobs: return jsonify({'error':'Job ne postoji'}), 404
    
    def generate():
        while True:
            job = jobs.get(job_id, {})
            if not job: break
            yield f"data: {json.dumps(job)}\n\n"
            if job.get('status') in ['Zavrseno'] or 'Greska' in job.get('status',''):
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
        result.append({'name':f, 'size_mb':round(os.path.getsize(path)/(1024*1024),1),
                      'date':time.strftime('%d.%m.%Y %H:%M', time.localtime(os.path.getmtime(path)))})
    return jsonify(result[:20])

@main_bp.route('/test-voice', methods=['POST'])
def test_voice():
    data = request.get_json()
    voice = data.get('voice','hr-HR-GabrijelaNeural')
    tts = TTSEngine()
    tmp = tts.stream_chapter('Dobar dan, ovo je test glasa.', voice=voice, max_chars=500)
    return send_file(tmp, mimetype='audio/mpeg')

@main_bp.route('/download/<filename>')
def download_file(filename):
    output_dir = os.path.abspath('output')
    filepath = os.path.abspath(os.path.join(output_dir, secure_filename(filename)))
    if not filepath.startswith(output_dir): abort(403)
    if not os.path.exists(filepath): return jsonify({'error':'Fajl ne postoji'}), 404
    return send_file(filepath, as_attachment=True, download_name=filename)

@main_bp.route('/history')
def conversion_history():
    from app.database import get_history
    return jsonify(get_history(20))

# ========== STRANICE ==========
@main_bp.route('/reader')
def reader_page():
    return render_template('reader.html')

@main_bp.route('/convert')
def convert_page():
    return render_template('convert.html')

@main_bp.route('/rules')
def rules_page():
    return render_template('rules.html')

# ========== REPLACEMENT API ==========
from app.replacer import NameReplacer

@main_bp.route('/profiles')
def list_profiles():
    return jsonify(NameReplacer().list_profiles())

@main_bp.route('/replacements', methods=['GET'])
def get_replacements():
    epub = request.args.get('epub','')
    return jsonify(NameReplacer().get_rules(epub or None))

@main_bp.route('/replacements', methods=['POST'])
def add_replacement():
    data = request.get_json()
    original = data.get('original','').strip()
    replacement = data.get('replacement','').strip()
    epub = data.get('epub','')
    if original and replacement:
        rules = NameReplacer().add_rule(original, replacement, epub or None)
        return jsonify({'success':True, 'rules':rules})
    return jsonify({'error':'Nedostaju podaci'}), 400

@main_bp.route('/replacements/<original>', methods=['DELETE'])
def delete_replacement(original):
    epub = request.args.get('epub','')
    rules = NameReplacer().remove_rule(original, epub or None)
    return jsonify({'success':True, 'rules':rules})

@main_bp.route('/replacements/preview', methods=['POST'])
def preview_replacements():
    data = request.get_json()
    text = data.get('text','')
    epub = data.get('epub','')
    replacer = NameReplacer()
    return jsonify({'changes':replacer.preview(text, epub or None), 'preview':replacer.apply(text, epub or None)[:500]})

@main_bp.route('/replacements/import', methods=['POST'])
def import_rules():
    data = request.get_json()
    rules_text = data.get('rules','')
    epub = data.get('epub','')
    result = NameReplacer().import_moonreader(rules_text, epub or None)
    return jsonify({'success':True, 'rules':result['rules']})

@main_bp.route('/replacements/export')
def export_rules():
    epub = request.args.get('epub','')
    return jsonify({'rules':NameReplacer().export_moonreader(epub or None)})

@main_bp.route('/replacements/merge-global')
def merge_global():
    epub = request.args.get('epub','')
    if not epub: return jsonify({'error':'Nedostaje epub'}), 400
    rules = NameReplacer().merge_global_to_book(epub)
    return jsonify({'success':True, 'rules':rules})
