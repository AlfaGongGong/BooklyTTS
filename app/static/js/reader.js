let allChapters = [], currentChapterIdx = 0, epubFilename = null;
let ttsJobId = null, ttsStopFlag = false, ttsRate = 1.0, ttsPaused = false;
let currentEngine = 'edge';

// ========== INICIJALIZACIJA ==========
async function init() {
    // Probaj učitati postojeći EPUB
    try {
        const r = await fetch('/get-chapters');
        const d = await r.json();
        if (d.chapters && d.chapters.length > 0) {
            allChapters = d.chapters;
            epubFilename = 'book.epub';
            document.getElementById('book-title-header').textContent = 'Učitana knjiga';
            renderChapterList();
            loadChapter(0);
            document.querySelector('.welcome-screen').style.display = 'none';
        }
    } catch(e) {
        console.log('Nema postojećeg EPUB-a');
    }
}

// ========== UPLOAD ==========
document.getElementById('epub-file').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    document.querySelector('.welcome-screen').innerHTML = '<p style="color:#aaa;">⏳ Upload...</p>';
    
    const fd = new FormData(); fd.append('epub_file', file);
    try {
        const r = await fetch('/upload-epub', { method: 'POST', body: fd });
        const d = await r.json();
        
        if (d.success) {
            epubFilename = d.filename;
            allChapters = d.chapters;
            document.getElementById('book-title-header').textContent = d.metadata.title;
            document.querySelector('.welcome-screen').style.display = 'none';
            renderChapterList();
            loadChapter(0);
        } else {
            alert('Greška: ' + d.error);
        }
    } catch(err) {
        alert('Greška pri uploadu: ' + err.message);
    }
});

// ========== POGLAVLJA ==========
function renderChapterList() {
    const list = document.getElementById('chapter-list');
    if (!allChapters || allChapters.length === 0) {
        list.innerHTML = '<p class="empty">Nema poglavlja</p>';
        return;
    }
    
    list.innerHTML = allChapters.map((c, i) => `
        <div class="chapter-link ${i === currentChapterIdx ? 'active' : ''}" 
             onclick="loadChapter(${i})" id="ch-link-${i}">
            ${i+1}. ${c.title || 'Poglavlje ' + (i+1)}
            <span class="badge">${Math.round((c.char_count || 0)/1000)}k</span>
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
    
    if (!allChapters || !allChapters[idx]) {
        document.getElementById('reader-content').innerHTML = '<p>Nema teksta za ovo poglavlje</p>';
        return;
    }
    
    const chapter = allChapters[idx];
    const text = chapter.text || '';
    const paragraphs = text.split('\n\n').filter(p => p.trim());
    
    document.getElementById('reader-content').innerHTML = `
        <h2>${chapter.title || 'Poglavlje ' + (idx+1)}</h2>
        ${paragraphs.length > 0 ? paragraphs.map(p => `<p>${p}</p>`).join('') : '<p>' + text + '</p>'}
    `;
    
    document.getElementById('reading-progress').textContent = 
        Math.round((idx + 1) / allChapters.length * 100) + '%';
    
    // Update sidebar
    document.querySelectorAll('.chapter-link').forEach(el => el.classList.remove('active'));
    const active = document.getElementById('ch-link-' + idx);
    if (active) {
        active.classList.add('active');
        active.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
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

// ========== TTS PANEL ==========
function toggleTTS() {
    const panel = document.getElementById('tts-panel');
    if (panel.style.display === 'none' || panel.style.display === '') {
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
    }
}

function updateTTSRate(val) {
    ttsRate = parseFloat(val);
    document.getElementById('rate-display').textContent = val + 'x';
}

// ========== TTS PLAYBACK ==========
async function ttsPlay() {
    if (!allChapters || allChapters.length === 0) {
        alert('Prvo uploaduj EPUB!');
        return;
    }
    
    ttsStopFlag = false;
    ttsPaused = false;
    
    document.getElementById('tts-play-btn').style.display = 'none';
    document.getElementById('tts-pause-btn').style.display = 'inline-block';
    document.getElementById('tts-stop-btn').style.display = 'inline-block';
    document.getElementById('tts-status').textContent = '⏳ Generišem...';
    
    const voice = document.getElementById('tts-voice').value;
    
    try {
        const r = await fetch('/stream-start', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                chapter: currentChapterIdx, 
                voice: voice
            })
        });
        const d = await r.json();
        
        if (d.job_id) {
            ttsJobId = d.job_id;
            ttsPlayNextChunk();
        } else if (d.error) {
            document.getElementById('tts-status').textContent = '❌ ' + d.error;
            resetTTSButtons();
        }
    } catch(e) {
        document.getElementById('tts-status').textContent = '❌ Greška';
        resetTTSButtons();
    }
}

async function ttsPlayNextChunk() {
    if (ttsStopFlag || ttsPaused || !ttsJobId) return;
    
    try {
        const r = await fetch('/stream-next/' + ttsJobId);
        const ct = r.headers.get('content-type') || '';
        
        if (ct.includes('audio')) {
            const blob = await r.blob();
            const audio = new Audio(URL.createObjectURL(blob));
            audio.playbackRate = ttsRate;
            await audio.play();
            document.getElementById('tts-status').textContent = '▶️ Reprodukcija...';
            audio.onended = () => { 
                if (!ttsStopFlag && !ttsPaused) ttsPlayNextChunk(); 
            };
        } else {
            const d = await r.json();
            if (d.finished) {
                document.getElementById('tts-status').textContent = '✅ Kraj poglavlja';
                resetTTSButtons();
                // Auto-next
                if (currentChapterIdx < allChapters.length - 1) {
                    setTimeout(() => { 
                        loadChapter(currentChapterIdx + 1); 
                        ttsPlay(); 
                    }, 1500);
                }
            } else if (d.error) {
                document.getElementById('tts-status').textContent = '❌ ' + d.error;
                resetTTSButtons();
            }
        }
    } catch(e) {
        document.getElementById('tts-status').textContent = '❌ Greška';
        resetTTSButtons();
    }
}

let activeAudio = null;
function ttsPause() {
    ttsPaused = !ttsPaused;
    document.getElementById('tts-pause-btn').textContent = ttsPaused ? '▶️ Nastavi' : '⏸️ Pauza';
    document.getElementById('tts-status').textContent = ttsPaused ? '⏸️ Pauzirano' : '▶️ Reprodukcija...';
    if (!ttsPaused) ttsPlayNextChunk();
}

function ttsStop() {
    ttsStopFlag = true; 
    ttsJobId = null;
    resetTTSButtons();
    document.getElementById('tts-status').textContent = '⏹️ Zaustavljeno';
}

function ttsNext() {
    if (allChapters.length > 0 && currentChapterIdx < allChapters.length - 1) {
        ttsStop();
        loadChapter(currentChapterIdx + 1);
        setTimeout(ttsPlay, 500);
    }
}

function ttsPrev() {
    if (currentChapterIdx > 0) {
        ttsStop();
        loadChapter(currentChapterIdx - 1);
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
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 'ArrowRight') ttsNext();
    if (e.key === 'ArrowLeft') ttsPrev();
    if (e.key === ' ') { e.preventDefault(); ttsPaused ? ttsPause() : ttsPlay(); }
});

// Init
init();

// ========== LOCAL STORAGE STATE ==========
function saveState() {
    const state = {
        chapter: currentChapterIdx,
        fontSize: document.getElementById('font-size').value,
        theme: document.body.classList.contains('light') ? 'light' : 'dark',
        sidebarOpen: document.getElementById('sidebar').classList.contains('open'),
        scrollPos: document.getElementById('reader-content').scrollTop
    };
    localStorage.setItem('booklytts_state', JSON.stringify(state));
}

function restoreState() {
    try {
        const state = JSON.parse(localStorage.getItem('booklytts_state'));
        if (state) {
            if (state.fontSize) changeFontSize(state.fontSize);
            if (state.theme === 'light') document.body.classList.add('light');
            if (state.sidebarOpen) document.getElementById('sidebar').classList.add('open');
        }
    } catch(e) {}
}

// Auto-save svakih 5s
setInterval(saveState, 5000);
document.getElementById('reader-content').addEventListener('scroll', saveState);
restoreState();
