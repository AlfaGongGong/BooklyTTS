let allChapters = [], currentChapterIdx = 0, epubFilename = null;
let ttsJobId = null, ttsStopFlag = false, ttsRate = 1.0, ttsPaused = false;
let activeAudio = null;

document.getElementById('epub-file').addEventListener('change', async function() {
    const file = this.files[0];
    if (!file) return;
    document.getElementById('upload-status').textContent = '⏳...';
    const fd = new FormData(); fd.append('epub_file', file);
    try {
        const r = await fetch('/upload-epub', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.success) {
            epubFilename = d.filename; allChapters = d.chapters;
            document.getElementById('book-title-header').textContent = d.metadata.title;
            document.getElementById('upload-status').textContent = '✅ ' + d.chapter_count + ' pogl.';
            document.querySelector('.welcome-screen').style.display = 'none';
            renderChapterList(); loadChapter(0);
        } else {
            document.getElementById('upload-status').textContent = '❌ ' + (d.error || 'Greška');
        }
    } catch(e) { document.getElementById('upload-status').textContent = '❌ Greška'; }
});

function renderChapterList() {
    const list = document.getElementById('chapter-list');
    if (!allChapters.length) { list.innerHTML = '<p class="empty">Nema poglavlja</p>'; return; }
    list.innerHTML = allChapters.map((c, i) => `
        <div class="chapter-link ${i === currentChapterIdx ? 'active' : ''}" onclick="loadChapter(${i})" id="ch-${i}">
            ${i+1}. ${c.title || 'Poglavlje '+(i+1)}
        </div>`).join('');
}
function filterChapters() {
    const q = document.getElementById('chapter-search').value.toLowerCase();
    document.querySelectorAll('.chapter-link').forEach(el => el.style.display = el.textContent.toLowerCase().includes(q) ? '' : 'none');
}
function loadChapter(idx) {
    currentChapterIdx = idx;
    if (!allChapters[idx]) return;
    const ch = allChapters[idx];
    document.getElementById('reader-content').innerHTML = `<h2>${ch.title || 'Poglavlje '+(idx+1)}</h2>` + (ch.text || '').split('\n\n').filter(p=>p.trim()).map(p=>`<p>${p}</p>`).join('');
    document.getElementById('reading-progress').textContent = Math.round((idx+1)/allChapters.length*100) + '%';
    document.querySelectorAll('.chapter-link').forEach(el => el.classList.remove('active'));
    const a = document.getElementById('ch-'+idx); if (a) { a.classList.add('active'); a.scrollIntoView({behavior:'smooth',block:'center'}); }
}
function toggleSidebar() { document.getElementById('sidebar').classList.toggle('open'); }
function changeFontSize(s) { document.getElementById('reader-content').style.fontSize = s + 'px'; localStorage.setItem('fontSize', s); }
function toggleTheme() { document.body.classList.toggle('light'); }
function updateRate(v) { ttsRate = parseFloat(v); document.getElementById('rate-display').textContent = v + 'x'; }

function toggleTTSPanel() {
    const p = document.getElementById('tts-panel');
    p.style.display = p.style.display === 'block' ? 'none' : 'block';
}

async function ttsPlay() {
    if (!allChapters.length) { alert('Uploaduj EPUB!'); return; }
    ttsStopFlag = false; ttsPaused = false;
    document.getElementById('tts-play-btn').style.display = 'none';
    document.getElementById('tts-pause-btn').style.display = 'inline-block';
    document.getElementById('tts-stop-btn').style.display = 'inline-block';
    document.getElementById('tts-status').textContent = '⏳ Generišem...';
    const voice = document.getElementById('tts-voice').value;
    try {
        const r = await fetch('/stream-start', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({chapter:currentChapterIdx, voice:voice, epub_filename:epubFilename}) });
        const d = await r.json();
        if (d.job_id) { ttsJobId = d.job_id; ttsPlayNextChunk(); }
        else { document.getElementById('tts-status').textContent = '❌ ' + (d.error||'Greška'); resetTTS(); }
    } catch(e) { document.getElementById('tts-status').textContent = '❌ Greška'; resetTTS(); }
}

async function ttsPlayNextChunk() {
    if (ttsStopFlag || ttsPaused || !ttsJobId) return;
    try {
        const r = await fetch('/stream-next/' + ttsJobId);
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('audio')) {
            const blob = await r.blob();
            if (activeAudio) { activeAudio.pause(); activeAudio = null; }
            activeAudio = new Audio(URL.createObjectURL(blob));
            activeAudio.playbackRate = ttsRate; activeAudio.play();
            document.getElementById('tts-status').textContent = '▶️ Reprodukcija...';
            activeAudio.onended = () => { if (!ttsStopFlag && !ttsPaused) ttsPlayNextChunk(); };
        } else {
            const d = await r.json();
            if (d.finished) { document.getElementById('tts-status').textContent = '✅ Kraj'; resetTTS(); }
        }
    } catch(e) { document.getElementById('tts-status').textContent = '❌ Greška'; resetTTS(); }
}

function ttsPause() {
    if (!activeAudio) return;
    if (ttsPaused) { activeAudio.play(); ttsPaused = false; document.getElementById('tts-pause-btn').textContent = '⏸️ Pauza'; }
    else { activeAudio.pause(); ttsPaused = true; document.getElementById('tts-pause-btn').textContent = '▶️ Nastavi'; }
}
function ttsStop() { ttsStopFlag = true; ttsJobId = null; if (activeAudio) { activeAudio.pause(); activeAudio = null; } resetTTS(); }
function ttsNext() { if (currentChapterIdx < allChapters.length-1) { ttsStop(); loadChapter(currentChapterIdx+1); setTimeout(ttsPlay, 300); } }
function ttsPrev() { if (currentChapterIdx > 0) { ttsStop(); loadChapter(currentChapterIdx-1); setTimeout(ttsPlay, 300); } }
function resetTTS() { document.getElementById('tts-play-btn').style.display = 'inline-block'; document.getElementById('tts-pause-btn').style.display = 'none'; document.getElementById('tts-stop-btn').style.display = 'none'; }

document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'ArrowRight') ttsNext();
    if (e.key === 'ArrowLeft') ttsPrev();
    if (e.key === ' ') { e.preventDefault(); if (ttsJobId && !ttsStopFlag) ttsPause(); else ttsPlay(); }
});

(function() {
    const fs = localStorage.getItem('fontSize');
    if (fs) { document.getElementById('font-size').value = fs; document.getElementById('reader-content').style.fontSize = fs + 'px'; }
})();
