import os
import tempfile
import queue
import threading
import uuid
import time
from flask import Blueprint, request, jsonify, send_file, after_this_request
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor

stream_bp = Blueprint('stream', __name__)
stream_buffers = {}


def find_epub(filename=None):
    if filename:
        path = f'uploads/{filename}'
        if os.path.exists(path):
            return path
    for f in os.listdir('uploads'):
        if f.endswith('.epub') and f != '.gitkeep':
            return f'uploads/{f}'
    return None


@stream_bp.route('/stream-start', methods=['POST'])
def stream_start():
    d = request.get_json()
    epub_path = find_epub(d.get('epub_filename'))
    if not epub_path:
        return jsonify({'error': 'Nema EPUB-a'}), 404

    chapters = EPUBProcessor().extract_chapters(epub_path)
    if not chapters:
        return jsonify({'error': 'Nema poglavlja'}), 500

    start = int(d.get('chapter', 0))
    voice = d.get('voice', 'hr-HR-GabrijelaNeural')

    job_id = uuid.uuid4().hex[:12]
    q = queue.Queue(maxsize=3)
    stream_buffers[job_id] = q

    def buf():
        tts = TTSEngine()
        for i in range(start, len(chapters)):
            text = chapters[i]['text']
            for j in range(0, len(text), 2000):
                chunk = text[j:j + 2000]
                if len(chunk.strip()) < 50:
                    continue
                tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                tts.synthesize(chunk, tmp.name, voice)
                q.put({'file': tmp.name, 'title': chapters[i]['title']})
        q.put({'done': True})

    threading.Thread(target=buf, daemon=True).start()
    return jsonify({'job_id': job_id, 'total': len(chapters)})


@stream_bp.route('/stream-next/<job_id>')
def stream_next(job_id):
    if job_id not in stream_buffers:
        return jsonify({'error': 'Sesija ne postoji'}), 404
    try:
        chunk = stream_buffers[job_id].get(timeout=120)
    except queue.Empty:
        return jsonify({'error': 'Timeout'}), 408
    if chunk.get('done'):
        del stream_buffers[job_id]
        return jsonify({'finished': True})

    file_path = chunk['file']

    @after_this_request
    def cleanup(response):
        try:
            os.remove(file_path)
        except Exception:
            pass
        return response

    return send_file(file_path, mimetype='audio/mpeg')


@stream_bp.route('/stream-from-text', methods=['POST'])
def stream_from_text():
    d = request.get_json()
    text = d.get('text', '')
    voice = d.get('voice', 'hr-HR-GabrijelaNeural')
    if not text:
        return jsonify({'error': 'Nema teksta'}), 400

    job_id = uuid.uuid4().hex[:12]
    q = queue.Queue(maxsize=3)
    stream_buffers[job_id] = q

    def buf():
        tts = TTSEngine()
        for j in range(0, len(text), 2000):
            chunk = text[j:j + 2000]
            if len(chunk.strip()) < 50:
                continue
            tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            tts.synthesize(chunk, tmp.name, voice)
            q.put({'file': tmp.name, 'title': 'Stream'})
        q.put({'done': True})

    threading.Thread(target=buf, daemon=True).start()
    return jsonify({'job_id': job_id})


@stream_bp.route('/get-chapters')
def get_chapters():
    epub_path = find_epub(request.args.get('epub'))
    if not epub_path:
        return jsonify({'chapters': []})
    chapters = EPUBProcessor().extract_chapters(epub_path)
    return jsonify({
        'chapters': [
            {'id': c['id'], 'title': c['title'],
             'char_count': c['char_count'], 'text': c['text']}
            for c in chapters
        ]
    })


@stream_bp.route('/find-sentence', methods=['POST'])
def find_sentence():
    d = request.get_json()
    search = d.get('sentence', '').strip().lower()
    if not search:
        return jsonify({'found': False})

    epub_path = find_epub(d.get('epub_filename'))
    if not epub_path:
        return jsonify({'found': False})

    chapters = EPUBProcessor().extract_chapters(epub_path)
    for i, ch in enumerate(chapters):
        pos = ch['text'].lower().find(search)
        if pos >= 0:
            text = ch['text']
            start = text.rfind('.', 0, pos)
            start = 0 if start == -1 else start + 2
            return jsonify({
                'found': True,
                'chapter_idx': i,
                'chapter_title': ch['title'],
                'text_from_position': text[start:],
                'total_chapters': len(chapters)
            })
    return jsonify({'found': False})


def cleanup_old_sessions():
    while True:
        time.sleep(300)
        for job_id in list(stream_buffers.keys()):
            try:
                if stream_buffers[job_id].qsize() == 0:
                    del stream_buffers[job_id]
            except Exception:
                pass


threading.Thread(target=cleanup_old_sessions, daemon=True).start()
