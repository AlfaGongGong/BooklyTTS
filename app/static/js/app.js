let uploadedEpub = null, chapters = [], selectedChapters = new Set();

// ========== STATUS ==========
async function checkStatus() {
    try {
        const r = await fetch('/status');
        const d = await r.json();
        document.getElementById('status-text').textContent = 'Edge TTS Spreman';
        document.getElementById('status-dot').classList.add('ready');
        document.getElementById('disk-info').textContent = 'Disk: ' + d.disk_free_mb + ' MB';
    } catch(e) {
        document.getElementById('status-text').textContent = 'Server nije dostupan';
    }
}

// ========== TOAST ==========
function showToast(msg, type='info') {
    const toast = document.getElementById('upload-toast');
    toast.textContent = msg;
    toast.className = 'toast ' + type;
    toast.classList.remove('hidden');
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

// ========== UPLOAD ==========
document.getElementById('upload-btn').addEventListener('click', async () => {
    const file = document.getElementById('epub-file').files[0];
    if (!file) { showToast('Odaberi EPUB fajl', 'error'); return; }
    
    showToast('⏳ Upload...', 'info');
    const fd = new FormData();
    fd.append('epub_file', file);
    
    try {
        const r = await fetch('/upload-epub', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.success) {
            uploadedEpub = d.filename;
            chapters = d.chapters;
            document.getElementById('epub-info').style.display = 'block';
            document.getElementById('epub-title').textContent = d.metadata.title;
            document.getElementById('epub-author').textContent = d.metadata.author;
            
            renderChapterList();
            document.getElementById('chapter-section').style.display = 'block';
            showToast('✅ ' + d.chapter_count + ' poglavlja', 'success');
        } else {
            showToast('❌ ' + d.error, 'error');
        }
    } catch(e) {
        showToast('❌ Greška', 'error');
    }
});

// ========== POGLAVLJA ==========
function renderChapterList() {
    const list = document.getElementById('chapter-list');
    selectedChapters = new Set(chapters.map(c => c.id));
    
    list.innerHTML = chapters.map(c => `
        <label class="chapter-item">
            <input type="checkbox" checked onchange="toggleChapter(${c.id})">
            <span>${c.title}</span>
            <span class="char-count">(${Math.round(c.char_count/1000)}k)</span>
        </label>
    `).join('');
    
    updateChapterCount();
}

function toggleChapter(id) {
    if (selectedChapters.has(id)) selectedChapters.delete(id);
    else selectedChapters.add(id);
    updateChapterCount();
}

function selectAllChapters() {
    chapters.forEach(c => selectedChapters.add(c.id));
    document.querySelectorAll('#chapter-list input').forEach(cb => cb.checked = true);
    updateChapterCount();
}

function deselectAllChapters() {
    selectedChapters.clear();
    document.querySelectorAll('#chapter-list input').forEach(cb => cb.checked = false);
    updateChapterCount();
}

function updateChapterCount() {
    document.getElementById('chapter-count').textContent = `(${selectedChapters.size}/${chapters.length} odabrano)`;
}

// ========== TEST GLASA ==========
async function testVoice() {
    const voice = document.getElementById('voice-select').value;
    const audio = document.getElementById('test-audio');
    audio.style.display = 'block';
    
    try {
        const r = await fetch('/test-voice', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({voice: voice})
        });
        const blob = await r.blob();
        audio.src = URL.createObjectURL(blob);
        audio.play();
    } catch(e) {
        showToast('❌ Greška pri testu glasa', 'error');
    }
}

// ========== KONVERZIJA ==========
document.getElementById('start-btn').addEventListener('click', async () => {
    if (!uploadedEpub) { showToast('Prvo uploaduj EPUB', 'error'); return; }
    if (selectedChapters.size === 0) { showToast('Odaberi bar jedno poglavlje', 'error'); return; }
    
    const voice = document.getElementById('voice-select').value;
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('start-btn').disabled = true;
    
    try {
        const r = await fetch('/start-conversion', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                epub_filename: uploadedEpub,
                voice: voice,
                chapters: [...selectedChapters]
            })
        });
        const d = await r.json();
        if (d.job_id) trackProgress(d.job_id);
    } catch(e) {
        showToast('❌ Greška', 'error');
        document.getElementById('start-btn').disabled = false;
    }
});

function trackProgress(jobId) {
    const es = new EventSource('/conversion-progress/' + jobId);
    es.onmessage = function(e) {
        const d = JSON.parse(e.data);
        document.getElementById('progress-fill').style.width = d.progress + '%';
        document.getElementById('progress-text').textContent = d.progress + '%';
        document.getElementById('progress-detail').textContent = d.status || '';
        
        if (d.status === 'Zavrseno') {
            document.getElementById('progress-text').textContent = '✅ Gotovo!';
            document.getElementById('start-btn').disabled = false;
            es.close();
            loadAudiobooks();
            setTimeout(() => {
                document.getElementById('progress-section').style.display = 'none';
            }, 3000);
        }
        if (d.status && d.status.startsWith('Greska')) {
            document.getElementById('progress-text').textContent = '❌ ' + d.status;
            document.getElementById('start-btn').disabled = false;
            es.close();
        }
    };
}

// ========== AUDIOBOOKOVI ==========
async function loadAudiobooks() {
    try {
        const r = await fetch('/list-audiobooks');
        const books = await r.json();
        const list = document.getElementById('audiobook-list');
        
        if (books.length === 0) {
            list.innerHTML = '<p class="empty">Nema audiobookova</p>';
        } else {
            list.innerHTML = books.map(b => `
                <div class="audiobook-item">
                    <span>🎧 ${b.name}</span>
                    <span class="book-info">${b.size_mb} MB · ${b.date}</span>
                    <a href="/download/${b.name}" class="btn btn-small btn-download">⬇️</a>
                </div>
            `).join('');
        }
    } catch(e) {
        document.getElementById('audiobook-list').innerHTML = '<p class="empty">Greška</p>';
    }
}

// Init
checkStatus();
loadAudiobooks();
setInterval(checkStatus, 60000);
