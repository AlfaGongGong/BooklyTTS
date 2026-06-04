let allChapters = [], currentChapterIdx = 0, epubFilename = null;
let ttsJobId = null, ttsStopFlag = false, ttsRate = 1.0, ttsPaused = false;

// ========== UPLOAD ==========
document.getElementById('epub-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const fd = new FormData(); fd.append('epub_file', file);
    const r = await fetch('/upload-epub', { method: 'POST', body: fd });
    const d = await r.json();
    
    if (d.success) {
        epubFilename = d.filename;
        allChapters = d.chapters;
        document.getElementById('book-title-header').textContent = d.metadata.title;
        renderChapterList();
        loadChapter(0);
    } else {
        alert(d.error);
    }
});

// ========== POGLAVLJA ==========
function renderChapterList() {
    const list = document.getElementById('chapter-list');
    list.innerHTML = allChapters.map((c, i) => `
        <div class="chapter-link ${i === currentChapterIdx ? 'active' : ''}" 
             onclick="loadChapter(${i})">
            ${i+1}. ${c.title}
            <span class="badge">${Math.round(c.char_count/1000)}k</span>
        </div>
    `).join('');
}

function filterChapters() {
    const q = document.getElementById('chapter-search').value.toLowerCase();
    document.querySelectorAll('.chapter-link').forEach(el => {
        el.style.display = el.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
}

async function loadChapter(idx) {
    currentChapterIdx = idx;
    document.getElementById('reader-content').innerHTML = '<p style="text-align:center;color:#aaa;">⏳ Učitavanje...</p>';
    renderChapterList();
    
    // Skrolaj do aktivnog poglavlja
    const active = document.querySelector('.chapter-link.active');
    if (active) active.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Učitaj tekst poglavlja
    const text = allChapters[idx].text;
    const paragraphs = text.split('\n\n');
    
    document.getElementById('reader-content').innerHTML = `
        <h2>${allChapters[idx].title}</h2>
        ${paragraphs.map(p => `<p>${p}</p>`).join('')}
    `;
    
    document.getElementById('reading-progress').textContent = 
        Math.round((idx + 1) / allChapters.length * 100) + '%';
}

// ========== ČITAČ KONTROLE ==========
function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
}

function changeFontSize(size) {
    document.getElementById('reader-content').style.fontSize = size + 'px';
}

function toggleTheme() {
    document.body.classList.toggle('light');
}

// ========== TTS ==========
function toggleTTS() {
    const panel = document.getElementById('tts-panel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
}

function toggleSettings() {
    alert('Podešavanja: izgovor, brzina, glas');
}

function updateTTSRate(val) {
    ttsRate = parseFloat(val);
    document.getElementById('rate-display').textContent = val + 'x';
}

async function ttsPlay() {
    ttsStopFlag = false;
    ttsPaused = false;
    
    document.getElementById('tts-play-btn').style.display = 'none';
    document.getElementById('tts-pause-btn').style.display = 'inline-block';
    document.getElementById('tts-stop-btn').style.display = 'inline-block';
    document.getElementById('tts-status').textContent = '⏳ Generišem...';
    
    const voice = document.getElementById('tts-voice').value;
    
    // Highlight trenutnu rečenicu
    const currentText = allChapters[currentChapterIdx].text;
    highlightCurrentSentence(currentText);
    
    const r = await fetch('/stream-start', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({chapter: currentChapterIdx, voice: voice})
    });
    const d = await r.json();
    if (d.job_id) { ttsJobId = d.job_id; ttsPlayNextChunk(); }
}

function highlightCurrentSentence(text) {
    // Podijeli na rečenice i označi prvu
    const sentences = text.split(/(?<=[.!?])\s+/);
    if (sentences.length > 0) {
        const highlighted = '<span class="highlight-sentence">' + sentences[0] + '</span> ' + 
                          sentences.slice(1).join(' ');
        document.getElementById('reader-content').innerHTML = 
            `<h2>${allChapters[currentChapterIdx].title}</h2><p>${highlighted}</p>`;
    }
}

async function ttsPlayNextChunk() {
    if (ttsStopFlag || ttsPaused || !ttsJobId) return;
    
    const r = await fetch('/stream-next/' + ttsJobId);
    const ct = r.headers.get('content-type') || '';
    
    if (ct.includes('audio')) {
        const blob = await r.blob();
        const audio = new Audio(URL.createObjectURL(blob));
        audio.playbackRate = ttsRate;
        audio.play();
        document.getElementById('tts-status').textContent = '▶️ Reprodukcija...';
        audio.onended = () => { if (!ttsStopFlag && !ttsPaused) ttsPlayNextChunk(); };
    } else {
        const d = await r.json();
        if (d.finished) {
            document.getElementById('tts-status').textContent = '✅ Kraj poglavlja';
            resetTTSButtons();
            // Auto-next
            if (currentChapterIdx < allChapters.length - 1) {
                setTimeout(() => { loadChapter(currentChapterIdx + 1); ttsPlay(); }, 1000);
            }
        }
    }
}

function ttsPause() {
    ttsPaused = !ttsPaused;
    document.getElementById('tts-pause-btn').textContent = ttsPaused ? '▶️ Nastavi' : '⏸️ Pauza';
    document.getElementById('tts-status').textContent = ttsPaused ? '⏸️ Pauzirano' : '▶️ Reprodukcija...';
    if (!ttsPaused) ttsPlayNextChunk();
}

function ttsStop() {
    ttsStopFlag = true; ttsJobId = null;
    resetTTSButtons();
    document.getElementById('tts-status').textContent = '⏹️ Zaustavljeno';
}

function ttsNext() {
    if (currentChapterIdx < allChapters.length - 1) {
        loadChapter(currentChapterIdx + 1);
        ttsStop();
        setTimeout(ttsPlay, 500);
    }
}

function ttsPrev() {
    if (currentChapterIdx > 0) {
        loadChapter(currentChapterIdx - 1);
        ttsStop();
        setTimeout(ttsPlay, 500);
    }
}

function resetTTSButtons() {
    document.getElementById('tts-play-btn').style.display = 'inline-block';
    document.getElementById('tts-pause-btn').style.display = 'none';
    document.getElementById('tts-stop-btn').style.display = 'none';
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight') ttsNext();
    if (e.key === 'ArrowLeft') ttsPrev();
    if (e.key === ' ') { e.preventDefault(); ttsPaused ? ttsPause() : ttsPlay(); }
});
