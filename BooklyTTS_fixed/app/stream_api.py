import os
import tempfile
import queue
import threading
import time
import uuid
from flask import Blueprint, request, jsonify, send_file, after_this_request
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor

stream_bp = Blueprint('stream', __name__)

# job_id -> {'q': Queue, 'created': float, 'done': bool}
_stream_meta = {}
_stream_lock = threading.Lock()

_EPUB_PROC = EPUBProcessor()   # ARCH-02: singleton

_JOB_TTL = 600  # 10 minuta


def _cleanup_stale_jobs():
    """Briše napuštene jobove starije od TTL-a."""
    cutoff = time.time() - _JOB_TTL
    with _stream_lock:
        dead = [k for k, v in _stream_meta.items() if v['created'] < cutoff]
        for k in dead:
            _stream_meta.pop(k, None)


def _register_job(job_id, q):
    _cleanup_stale_jobs()
    with _stream_lock:
        _stream_meta[job_id] = {'q': q, 'created': time.time(), 'done': False}


def _remove_job(job_id):
    with _stream_lock:
        _stream_meta.pop(job_id, None)


def _job_exists(job_id):
    with _stream_lock:
        return job_id in _stream_meta


def find_epub(filename=None):
    """Vraća putanju EPUB-a. Bez filename → 400, bez fallback random logike."""
    if not filename:
        return None
    path = f'uploads/{filename}'
    return path if os.path.exists(path) else None


def clean_header(val):
    """Ukloni SVE problematicne karaktere iz headera."""
    if not val:
        return ''
    return str(val).replace('\n', ' ').replace('\r', '').encode(
        'ascii', 'ignore').decode('ascii')[:200]


def _buf_worker(job_id, q, chapters, start, voice, epub_name):
    """
    Worker thread koji šalje chunkove u queue.
    ARCH-01: koristi put_nowait + Full handling — ne blokira zauvijek.
    ARCH-03: jedan asyncio event loop za cijeli job.
    ARCH-05: prosljeđuje epub_name za per-book zamjene.
    """
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        tts = TTSEngine()
        for i in range(start, len(chapters)):
            # Provjeri je li job još živ (TTL ili explicit remove)
            if not _job_exists(job_id):
                return

            text = chapters[i]['text']
            for j in range(0, len(text), 2000):
                if not _job_exists(job_id):
                    return

                chunk = text[j:j + 2000]
                if len(chunk.strip()) < 50:
                    continue

                tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)

                # ARCH-05: prosljeđuj epub_name
                tts.synthesize(chunk, tmp.name, voice,
                               epub_name=epub_name, loop=loop)

                item = {
                    'file': tmp.name,
                    'chapter_idx': i,
                    'chunk_idx': j // 2000,
                    'total_chunks': max(1, len(text) // 2000 + 1),
                    'total_chapters': len(chapters),
                    'text_snippet': chunk[:300]
                }

                # ARCH-01: put s timeoutom — ne blokira vječno ako klijent nestane
                try:
                    q.put(item, timeout=30)
                except queue.Full:
                    # Klijent ne čita (abandoned) — cleanup i izlaz
                    try:
                        os.remove(tmp.name)
                    except OSError:
                        pass
                    _remove_job(job_id)
                    return

        try:
            q.put({'done': True}, timeout=30)
        except queue.Full:
            pass
    finally:
        loop.close()


@stream_bp.route('/stream-start', methods=['POST'])
def stream_start():
    d = request.get_json()
    epub_filename = d.get('epub_filename')
    epub_path = find_epub(epub_filename)
    if not epub_path:
        return jsonify({'error': 'epub_filename je obavezan i mora postojati'}), 400

    # ARCH-02: singleton EPUBProcessor — lru_cache stvarno radi
    chapters = _EPUB_PROC.extract_chapters(epub_path)
    if not chapters:
        return jsonify({'error': 'Nema poglavlja'}), 500

    start = int(d.get('chapter', 0))
    voice = d.get('voice', 'hr-HR-GabrijelaNeural')
    epub_name = os.path.splitext(os.path.basename(epub_path))[0]

    job_id = uuid.uuid4().hex[:12]
    q = queue.Queue(maxsize=3)
    _register_job(job_id, q)

    threading.Thread(
        target=_buf_worker,
        args=(job_id, q, chapters, start, voice, epub_name),
        daemon=True
    ).start()

    return jsonify({'job_id': job_id, 'total': len(chapters)})


@stream_bp.route('/stream-next/<job_id>')
def stream_next(job_id):
    if not _job_exists(job_id):
        return jsonify({'error': 'Sesija ne postoji ili je istekla'}), 404

    with _stream_lock:
        meta = _stream_meta.get(job_id)
    if not meta:
        return jsonify({'error': 'Sesija ne postoji'}), 404

    try:
        chunk = meta['q'].get(timeout=120)
    except queue.Empty:
        return jsonify({'error': 'Timeout'}), 408

    if chunk.get('done'):
        _remove_job(job_id)
        return jsonify({'finished': True})

    file_path = chunk['file']

    @after_this_request
    def cleanup(response):
        try:
            os.remove(file_path)
        except OSError:
            pass
        return response

    resp = send_file(file_path, mimetype='audio/mpeg')
    resp.headers['X-Ch-Idx'] = str(chunk.get('chapter_idx', 0))
    resp.headers['X-Ck-Idx'] = str(chunk.get('chunk_idx', 0))
    resp.headers['X-Ck-Total'] = str(chunk.get('total_chunks', 1))
    resp.headers['X-Ch-Total'] = str(chunk.get('total_chapters', 1))
    return resp


@stream_bp.route('/stream-from-text', methods=['POST'])
def stream_from_text():
    d = request.get_json()
    text = d.get('text', '')
    voice = d.get('voice', 'hr-HR-GabrijelaNeural')
    if not text:
        return jsonify({'error': 'Nema teksta'}), 400

    job_id = uuid.uuid4().hex[:12]
    q = queue.Queue(maxsize=3)
    _register_job(job_id, q)

    # Simuliramo jedno pseudo-poglavlje za isti worker
    pseudo_chapters = [{'text': text, 'id': 0, 'title': 'Tekst',
                        'char_count': len(text)}]

    threading.Thread(
        target=_buf_worker,
        args=(job_id, q, pseudo_chapters, 0, voice, None),
        daemon=True
    ).start()

    return jsonify({'job_id': job_id})


@stream_bp.route('/get-chapters')
def get_chapters():
    epub_filename = request.args.get('epub')
    epub_path = find_epub(epub_filename)
    if not epub_path:
        return jsonify({'error': 'epub parametar je obavezan'}), 400

    # ARCH-02: singleton
    chapters = _EPUB_PROC.extract_chapters(epub_path)
    return jsonify({'chapters': [
        {'id': c['id'], 'title': c['title'],
         'char_count': c['char_count'], 'text': c['text']}
        for c in chapters
    ]})


@stream_bp.route('/find-sentence', methods=['POST'])
def find_sentence():
    d = request.get_json()
    search = d.get('sentence', '').strip().lower()
    if not search:
        return jsonify({'found': False})

    epub_path = find_epub(d.get('epub_filename'))
    if not epub_path:
        return jsonify({'found': False})

    # ARCH-02: singleton
    chapters = _EPUB_PROC.extract_chapters(epub_path)
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
