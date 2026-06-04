let uploadedEpub = null;
document.getElementById('epub-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    try {
        const response = await fetch('/upload-epub', { method: 'POST', body: formData });
        const data = await response.json();
        if (data.success) {
            uploadedEpub = data.filename;
            document.getElementById('epub-info').style.display = 'block';
            document.getElementById('epub-title').textContent = data.metadata.title;
            document.getElementById('epub-author').textContent = data.metadata.author;
            document.getElementById('epub-chapters').textContent = data.chapter_count;
            alert('EPUB uploadovan! ' + data.chapter_count + ' poglavlja.');
        } else { alert(data.error); }
    } catch (err) { alert('Greska: ' + err.message); }
});

document.getElementById('start-conversion').addEventListener('click', async () => {
    if (!uploadedEpub) { alert('Prvo uploaduj EPUB!'); return; }
    const voice = document.getElementById('voice-select').value;
    document.getElementById('progress').style.display = 'block';
    document.getElementById('start-conversion').disabled = true;
    document.getElementById('progress-text').textContent = '⏳ Konverzija u toku...';
    try {
        const response = await fetch('/start-conversion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ epub_filename: uploadedEpub, voice: voice })
        });
        const data = await response.json();
        if (data.success) {
            document.getElementById('progress-text').textContent = '✅ ' + data.message;
            setTimeout(() => location.reload(), 2000);
        } else {
            document.getElementById('progress-text').textContent = '❌ ' + data.error;
            document.getElementById('start-conversion').disabled = false;
        }
    } catch (err) {
        document.getElementById('progress-text').textContent = '❌ Greska: ' + err.message;
        document.getElementById('start-conversion').disabled = false;
    }
});
