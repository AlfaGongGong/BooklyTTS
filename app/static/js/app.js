// ========== ZAJEDNIČKE VARIJABLE ==========
let allChapters = [], uploadedEpub = null;

// ========== TAB SWITCH ==========
function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
    if (tab === 'convert') { checkStatus(); loadAudiobooks(); }
}

// ========== UPLOAD (zajednički) ==========
function showToast(msg, type='info') {
    const t = document.getElementById('upload-toast');
    t.textContent = msg; t.className = 'toast ' + type; t.classList.remove('hidden');
    setTimeout(() => t.classList.add('hidden'), 3000);
}

document.getElementById('upload-btn').addEventListener('click', async () => {
    const file = document.getElementById('epub-file').files[0];
    if (!file) { showToast('Odaberi EPUB fajl', 'error'); return; }
    
    showToast('⏳ Upload...', 'info');
    const fd = new FormData(); fd.append('epub_file', file);
    
    try {
        const r = await fetch('/upload-epub', { method: 'POST', body: fd });
        const d = await r.json();
        
        if (d.success) {
            uploadedEpub = d.filename;
            allChapters = d.chapters;
            
            // Zajednički info
            document.getElementById('epub-info').style.display = 'block';
            document.getElementById('epub-title').textContent = d.metadata.title;
            document.getElementById('epub-author').textContent = d.metadata.author;
            document.getElementById('epub-chapters-count').textContent = d.chapter_count;
            
            // Popuni player selector
            const sel = document.getElementById('chapter-select-listen');
            sel.innerHTML = '<option value="0">Od početka</option>' + 
                d.chapters.map((c, i) => `<option value="${i}">${i+1}. ${c.title}</option>`).join('');
            
            // Popuni konverter listu
            renderChapterList();
            document.getElementById('chapter-section').style.display = 'block';
            
            // Prikaži tabove
            document.getElementById('tabs-section').style.display = 'flex';
            
            showToast('✅ ' + d.chapter_count + ' poglavlja učitano', 'success');
        } else {
            showToast('❌ ' + d.error, 'error');
        }
    } catch(e) {
        showToast('❌ Greška pri uploadu', 'error');
    }
});

// ========== PLAYER (LISTEN TAB) ==========
let currentChapter = 0, currentJobId = null, stopFlag = false, currentRate = 1.0;

function updateChapterTitle() {
    currentChapter = parseInt(document.getElementById('chapter-select-listen').value);
    if (allChapters[currentChapter]) {
        document.getElementById('chapter-title-display').textContent = '📖 ' + allChapters[currentChapter].title;
    }
}

function updateRate(val) {
    currentRate = parseFloat(val);
    document.getElementById('rate-value').textContent = val + 'x';
    document.getElementById('audio-player').playbackRate = currentRate;
}

async function startPlayback() {
    if (!uploadedEpub) { showToast('Prvo uploaduj EPUB!', 'error'); return; }
    
    stopFlag = false;
    const voice = document.getElementById('voice-select-listen').value;
    const searchText = document.getElementById('search-input-listen').value.trim();
    currentChapter = parseInt(document.getElementById('chapter-select-listen').value);
    
    document.getElementById('play-btn-listen').style.display = 'none';
    document.getElementById('stop-btn-listen').style.display = 'inline-block';
    document.getElementById('listen-status').textContent = '⏳ Generišem...';
    
    try {
        let resp;
        if (searchText) {
            const fr = await fetch('/find-sentence', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({sentence: searchText})
            });
            const fd = await fr.json();
            if (fd.found) {
                currentChapter = fd.chapter_idx;
                document.getElementById('chapter-select-listen').value = currentChapter;
                document.getElementById('chapter-title-display').textContent = '📖 ' + fd.chapter_title;
                resp = await fetch('/stream-from-text', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: fd.text_from_position, voice: voice})
                });
            } else {
                document.getElementById('listen-status').textContent = '❌ Rečenica nije pronađena';
                document.getElementById('play-btn-listen').style.display = 'inline-block';
                document.getElementById('stop-btn-listen').style.display = 'none';
                return;
            }
        } else {
            updateChapterTitle();
            resp = await fetch('/stream-start', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({chapter: currentChapter, voice: voice})
            });
        }
        const data = await resp.json();
        if (data.job_id) { currentJobId = data.job_id; playNextChunk(); }
    } catch(e) {
        document.getElementById('listen-status').textContent = '❌ Greška';
        document.getElementById('play-btn-listen').style.display = 'inline-block';
        document.getElementById('stop-btn-listen').style.display = 'none';
    }
}

async function playNextChunk() {
    if (stopFlag || !currentJobId) return;
    try {
        const resp = await fetch('/stream-next/' + currentJobId);
        const ct = resp.headers.get('content-type') || '';
        if (ct.includes('audio')) {
            const blob = await resp.blob();
            const audio = document.getElementById('audio-player');
            audio.src = URL.createObjectURL(blob);
            audio.playbackRate = currentRate;
            audio.play();
            document.getElementById('listen-status').textContent = '▶️ Reprodukcija...';
            audio.onended = () => { if (!stopFlag) playNextChunk(); };
        } else {
            const data = await resp.json();
            if (data.finished) {
                document.getElementById('listen-status').textContent = '✅ Kraj';
                document.getElementById('play-btn-listen').style.display = 'inline-block';
                document.getElementById('stop-btn-listen').style.display = 'none';
            }
        }
    } catch(e) { if (!stopFlag) setTimeout(playNextChunk, 1000); }
}

function stopPlayback() {
    stopFlag = true; currentJobId = null;
    document.getElementById('audio-player').pause();
    document.getElementById('play-btn-listen').style.display = 'inline-block';
    document.getElementById('stop-btn-listen').style.display = 'none';
    document.getElementById('listen-status').textContent = '⏹️ Zaustavljeno';
}

function nextChapter() {
    if (currentChapter < allChapters.length - 1) {
        currentChapter++;
        document.getElementById('chapter-select-listen').value = currentChapter;
        updateChapterTitle();
    }
}

function prevChapter() {
    if (currentChapter > 0) {
        currentChapter--;
        document.getElementById('chapter-select-listen').value = currentChapter;
        updateChapterTitle();
    }
}

// ========== KONVERTER (CONVERT TAB) ==========
let selectedChapters = new Set();

async function checkStatus() {
    try {
        const r = await fetch('/status'); const d = await r.json();
        document.getElementById('status-text').textContent = 'Edge TTS Spreman';
        document.getElementById('status-dot').classList.add('ready');
        document.getElementById('disk-info').textContent = 'Disk: ' + d.disk_free_mb + ' MB';
    } catch(e) {}
}

function renderChapterList() {
    selectedChapters = new Set(allChapters.map(c => c.id));
    document.getElementById('chapter-list').innerHTML = allChapters.map(c => `
        <label class="chapter-item">
            <input type="checkbox" checked onchange="toggleChapter(${c.id})">
            <span>${c.title}</span>
            <span class="char-count">(${Math.round(c.char_count/1000)}k)</span>
        </label>
    `).join('');
    updateChapterCount();
}

function toggleChapter(id) {
    selectedChapters.has(id) ? selectedChapters.delete(id) : selectedChapters.add(id);
    updateChapterCount();
}
function selectAllChapters() { allChapters.forEach(c => selectedChapters.add(c.id)); renderChapterList(); }
function deselectAllChapters() { selectedChapters.clear(); renderChapterList(); }
function updateChapterCount() {
    document.getElementById('chapter-count').textContent = `(${selectedChapters.size}/${allChapters.length})`;
}

async function testVoice() {
    const voice = document.getElementById('voice-select-convert').value;
    const audio = document.getElementById('test-audio'); audio.style.display = 'block';
    try {
        const r = await fetch('/test-voice', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({voice}) });
        const blob = await r.blob(); audio.src = URL.createObjectURL(blob); audio.play();
    } catch(e) { showToast('❌ Greška', 'error'); }
}

document.getElementById('start-btn').addEventListener('click', async () => {
    if (!uploadedEpub) { showToast('Uploaduj EPUB', 'error'); return; }
    if (selectedChapters.size === 0) { showToast('Odaberi poglavlja', 'error'); return; }
    
    const voice = document.getElementById('voice-select-convert').value;
    document.getElementById('progress-section').style.display = 'block';
    document.getElementById('start-btn').disabled = true;
    
    try {
        const r = await fetch('/start-conversion', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({epub_filename: uploadedEpub, voice: voice, chapters: [...selectedChapters]})
        });
        const d = await r.json();
        if (d.job_id) trackProgress(d.job_id);
    } catch(e) { showToast('❌ Greška', 'error'); document.getElementById('start-btn').disabled = false; }
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
            document.getElementById('start-btn').disabled = false; es.close(); loadAudiobooks();
            setTimeout(() => document.getElementById('progress-section').style.display = 'none', 3000);
        }
    };
}

async function loadAudiobooks() {
    try {
        const r = await fetch('/list-audiobooks'); const books = await r.json();
        document.getElementById('audiobook-list').innerHTML = books.length === 0 ? 
            '<p class="empty">Nema audiobookova</p>' :
            books.map(b => `<div class="audiobook-item"><span>🎧 ${b.name}</span><span class="book-info">${b.size_mb} MB · ${b.date}</span><a href="/download/${b.name}" class="btn btn-small btn-download">⬇️</a></div>`).join('');
    } catch(e) {}
}

// Init
checkStatus();
loadAudiobooks();
setInterval(checkStatus, 60000);
