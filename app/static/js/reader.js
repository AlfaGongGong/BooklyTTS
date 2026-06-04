let allChapters = [], currentChapterIdx = 0, epubFilename = null;
let ttsJobId = null, ttsStopFlag = false, ttsRate = 1.0, ttsPaused = false;
let activeAudio = null;

// ========== UPLOAD ==========
document.getElementById('epub-file').addEventListener('change', async function() {
    const file = this.files[0];
    if (!file) return;
    
    document.getElementById('upload-status').textContent = '⏳ Upload...';
    
    const fd = new FormData();
    fd.append('epub_file', file);
    
    try {
        const r = await fetch('/upload-epub', { method: 'POST', body: fd });
        const d = await r.json();
        
        if (d.success) {
            epubFilename = d.filename;
            allChapters = d.chapters;
            document.getElementById('book-title-header').textContent = d.metadata.title;
            document.getElementById('upload-status').textContent = '✅ ' + d.chapter_count + ' poglavlja';
            document.querySelector('.welcome-screen').style.display = 'none';
            renderChapterList();
            loadChapter(0);
            saveState();
        } else {
            document.getElementById('upload-status').textContent = '❌ ' + (d.error || 'Greška');
        }
    } catch(e) {
        document.getElementById('upload-status').textContent = '❌ Greška';
    }
});

// ========== POGLAVLJA ==========
function renderChapterList() {
    const list = document.getElementById('chapter-list');
    if (!allChapters.length) {
        list.innerHTML = '<p class="empty">Nema poglavlja</p>';
        return;
    }
    list.innerHTML = allChapters.map((c, i) => `
        <div class="chapter-link ${i === currentChapterIdx ? 'active' : ''}" 
             onclick="loadChapter(${i})" id="ch-${i}">
            ${i+1}. ${c.title || 'Poglavlje '+(i+1)}
        </div>
    `).join('');
}

function filterChapters() {
    const q = document.getElementById('chapter-search').value.toLowerCase();
    document.querySelectorAll('.chapter-link').forEach(el => {
        el.style.display = el.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
}

function loadChapter(idx) {
    currentChapterIdx = idx;
    if (!allChapters[idx]) return;
    
    const ch = allChapters[idx];
    document.getElementById('reader-content').innerHTML = 
        `<h2>${ch.title || 'Poglavlje '+(idx+1)}</h2>` +
        (ch.text || '').split('\n\n').filter(p=>p.trim()).map(p=>`<p>${p}</p>`).join('');
    
    document.getElementById('reading-progress').textContent = 
        Math.round((idx+1)/allChapters.length*100) + '%';
    
    // Update sidebar
    document.querySelectorAll('.chapter-link').forEach(el => el.classList.remove('active'));
    const active = document.getElementById('ch-'+idx);
    if (active) { active.classList.add('active'); active.scrollIntoView({behavior:'smooth',block:'center'}); }
    
    saveState();
}

// ========== TOOLBAR ==========
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}
function changeFontSize(size) {
    document.getElementById('reader-content').style.fontSize = size + 'px';
    localStorage.setItem('fontSize', size);
}
function toggleTheme() {
    document.body.classList.toggle('light');
    saveState();
}
function updateRate(val) {
    ttsRate = parseFloat(val);
    document.getElementById('rate-display').textContent = val + 'x';
}

// ========== TTS PANEL ==========
function toggleTTSPanel() {
    const panel = document.getElementById('tts-panel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

// ========== TTS PLAYBACK ==========
async function ttsPlay() {
    if (!allChapters.length) { alert('Uploaduj EPUB!'); return; }
    
    ttsStopFlag = false; ttsPaused = false;
    document.getElementById('tts-play-btn').style.display = 'none';
    document.getElementById('tts-pause-btn').style.display = 'inline-block';
    document.getElementById('tts-pause-btn').textContent = '⏸️ Pauza';
    document.getElementById('tts-stop-btn').style.display = 'inline-block';
    document.getElementById('tts-status').textContent = '⏳ Generišem...';
    
    const voice = document.getElementById('tts-voice').value;
    
    try {
        const r = await fetch('/stream-start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({chapter: currentChapterIdx, voice: voice, epub_filename: epubFilename})
        });
        const d = await r.json();
        if (d.job_id) { ttsJobId = d.job_id; ttsPlayNextChunk(); }
        else { document.getElementById('tts-status').textContent = '❌ ' + (d.error || 'Greška'); resetTTS(); }
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
            activeAudio.playbackRate = ttsRate;
            activeAudio.play();
            document.getElementById('tts-status').textContent = '▶️ Reprodukcija...';
            activeAudio.onended = () => { if (!ttsStopFlag && !ttsPaused) ttsPlayNextChunk(); };
        } else {
            const d = await r.json();
            if (d.finished) {
                document.getElementById('tts-status').textContent = '✅ Kraj poglavlja';
                resetTTS();
                if (currentChapterIdx < allChapters.length - 1) {
                    setTimeout(() => { loadChapter(currentChapterIdx + 1); ttsPlay(); }, 1000);
                }
            }
        }
    } catch(e) { document.getElementById('tts-status').textContent = '❌ Greška'; resetTTS(); }
}

function ttsPause() {
    if (!activeAudio) return;
    if (ttsPaused) {
        activeAudio.play();
        ttsPaused = false;
        document.getElementById('tts-pause-btn').textContent = '⏸️ Pauza';
        document.getElementById('tts-status').textContent = '▶️ Reprodukcija...';
        ttsPlayNextChunk();
    } else {
        activeAudio.pause();
        ttsPaused = true;
        document.getElementById('tts-pause-btn').textContent = '▶️ Nastavi';
        document.getElementById('tts-status').textContent = '⏸️ Pauzirano';
    }
}

function ttsStop() {
    ttsStopFlag = true; ttsJobId = null;
    if (activeAudio) { activeAudio.pause(); activeAudio = null; }
    resetTTS();
    document.getElementById('tts-status').textContent = '⏹️ Zaustavljeno';
}

function ttsNext() {
    if (currentChapterIdx < allChapters.length - 1) {
        ttsStop(); loadChapter(currentChapterIdx + 1); setTimeout(ttsPlay, 300);
    }
}
function ttsPrev() {
    if (currentChapterIdx > 0) {
        ttsStop(); loadChapter(currentChapterIdx - 1); setTimeout(ttsPlay, 300);
    }
}

function resetTTS() {
    document.getElementById('tts-play-btn').style.display = 'inline-block';
    document.getElementById('tts-pause-btn').style.display = 'none';
    document.getElementById('tts-stop-btn').style.display = 'none';
}

// ========== LOCAL STORAGE ==========
function saveState() {
    const s = {
        chapter: currentChapterIdx,
        fontSize: document.getElementById('font-size').value,
        theme: document.body.classList.contains('light') ? 'light' : 'dark',
        sidebarOpen: document.getElementById('sidebar').classList.contains('open')
    };
    localStorage.setItem('booklytts', JSON.stringify(s));
}
setInterval(saveState, 5000);

(function() {
    try {
        const s = JSON.parse(localStorage.getItem('booklytts'));
        if (s && s.fontSize) {
            document.getElementById('font-size').value = s.fontSize;
            document.getElementById('reader-content').style.fontSize = s.fontSize + 'px';
        }
        if (s && s.theme === 'light') document.body.classList.add('light');
    } catch(e) {}
})();

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'ArrowRight') ttsNext();
    if (e.key === 'ArrowLeft') ttsPrev();
    if (e.key === ' ') { e.preventDefault(); if (ttsJobId && !ttsStopFlag) ttsPause(); else ttsPlay(); }
});
