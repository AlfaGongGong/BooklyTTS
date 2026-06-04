let allChapters=[],currentIdx=0,epubFile=null,ttsJob=null,stopFlag=false,rate=1.0,paused=false,audio=null;

// ========== UPLOAD ==========
document.getElementById('epub-file').addEventListener('change',async function(){
    const f=this.files[0];if(!f)return;
    document.getElementById('upload-status').textContent='⏳...';
    const fd=new FormData();fd.append('epub_file',f);
    try{
        const r=await fetch('/upload-epub',{method:'POST',body:fd});
        const d=await r.json();
        if(d.success){
            epubFile=d.filename;allChapters=d.chapters;
            document.getElementById('book-title').textContent=d.metadata.title;
            document.getElementById('upload-status').textContent='✅ '+d.chapter_count+' pogl.';
            document.querySelector('.welcome').style.display='none';
            renderChapters();loadChapter(0);
        }else{document.getElementById('upload-status').textContent='❌ '+d.error}
    }catch(e){document.getElementById('upload-status').textContent='❌ Greška'}
});

// ========== POGLAVLJA ==========
function renderChapters(){
    const l=document.getElementById('chapter-list');
    l.innerHTML=allChapters.map((c,i)=>`<div class="chapter-item${i===currentIdx?' active':''}" onclick="loadChapter(${i})" id="ch-${i}">${i+1}. ${c.title||'Poglavlje '+(i+1)}</div>`).join('');
}
function filterChapters(){
    const q=document.getElementById('chapter-search').value.toLowerCase();
    document.querySelectorAll('.chapter-item').forEach(el=>el.style.display=el.textContent.toLowerCase().includes(q)?'':'none');
}
function loadChapter(i){
    currentIdx=i;if(!allChapters[i])return;
    const c=allChapters[i];
    document.getElementById('reader-content').innerHTML=`<h2>${c.title||'Poglavlje '+(i+1)}</h2>`+(c.text||'').split('\n\n').filter(p=>p.trim()).map(p=>`<p>${p}</p>`).join('');
    document.getElementById('progress-text').textContent=Math.round((i+1)/allChapters.length*100)+'%';
    document.querySelectorAll('.chapter-item').forEach(el=>el.classList.remove('active'));
    const a=document.getElementById('ch-'+i);if(a){a.classList.add('active');a.scrollIntoView({behavior:'smooth',block:'center'})}
}

// ========== TOOLBAR ==========
function toggleSidebar(){document.getElementById('sidebar').style.display=document.getElementById('sidebar').style.display==='none'?'flex':'none'}
function changeFontSize(s){document.getElementById('reader-content').style.fontSize=s+'px';localStorage.setItem('fs',s)}
function toggleTheme(){document.body.style.background=document.body.style.background==='#0d1117'?'#fff':'#0d1117';document.body.style.color=document.body.style.color==='#e6edf3'?'#24292f':'#e6edf3'}
function updateRate(v){rate=parseFloat(v);document.getElementById('rate-val').textContent=v+'x';if(audio)audio.playbackRate=rate}

// ========== TTS PANEL ==========
function toggleTTS(){
    const b=document.getElementById('tts-bar');
    b.style.display=b.style.display==='none'?'block':'none';
}

// ========== PRETRAGA REČENICE ==========
async function searchSentence(){
    const q=document.getElementById('sentence-search').value.trim();
    if(!q)return;
    document.getElementById('search-result').textContent='🔍 Tražim...';
    try{
        const r=await fetch('/find-sentence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sentence:q,epub_filename:epubFile})});
        const d=await r.json();
        if(d.found){
            document.getElementById('search-result').textContent='✅ Pogl. '+(d.chapter_idx+1)+': '+d.chapter_title;
            loadChapter(d.chapter_idx);
        }else{
            document.getElementById('search-result').textContent='❌ Nije pronađeno';
        }
    }catch(e){document.getElementById('search-result').textContent='❌ Greška'}
}

// ========== TTS PLAYBACK ==========
async function ttsPlay(){
    if(!allChapters.length){alert('Uploaduj EPUB!');return}
    stopFlag=false;paused=false;
    document.getElementById('btn-play').style.display='none';
    document.getElementById('btn-pause').style.display='inline-block';
    document.getElementById('btn-stop').style.display='inline-block';
    document.getElementById('tts-status').textContent='⏳ Generišem...';
    
    const voice=document.getElementById('tts-voice').value;
    try{
        const r=await fetch('/stream-start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chapter:currentIdx,voice:voice,epub_filename:epubFile})});
        const d=await r.json();
        if(d.job_id){ttsJob=d.job_id;playNext()}
        else{document.getElementById('tts-status').textContent='❌ '+(d.error||'Greška');resetBtns()}
    }catch(e){document.getElementById('tts-status').textContent='❌ Greška';resetBtns()}
}

async function playNext(){
    if(stopFlag||paused||!ttsJob)return;
    try{
        const r=await fetch('/stream-next/'+ttsJob);
        const ct=r.headers.get('content-type')||'';
        if(ct.includes('audio')){
            const blob=await r.blob();
            if(audio){audio.pause();audio=null}
            audio=new Audio(URL.createObjectURL(blob));
            audio.playbackRate=rate;audio.play();
            document.getElementById('tts-status').textContent='▶️ Reprodukcija...';
            audio.onended=()=>{if(!stopFlag&&!paused)playNext()};
        }else{
            const d=await r.json();
            if(d.finished){document.getElementById('tts-status').textContent='✅ Kraj poglavlja';resetBtns()}
        }
    }catch(e){document.getElementById('tts-status').textContent='❌ Greška';resetBtns()}
}

function ttsPause(){
    if(!audio)return;
    if(paused){audio.play();paused=false;document.getElementById('btn-pause').textContent='⏸️ Pauza';document.getElementById('tts-status').textContent='▶️ Reprodukcija...';playNext()}
    else{audio.pause();paused=true;document.getElementById('btn-pause').textContent='▶️ Nastavi';document.getElementById('tts-status').textContent='⏸️ Pauzirano'}
}
function ttsStop(){stopFlag=true;ttsJob=null;if(audio){audio.pause();audio=null}resetBtns();document.getElementById('tts-status').textContent='⏹️ Zaustavljeno'}
function ttsNext(){if(currentIdx<allChapters.length-1){ttsStop();loadChapter(currentIdx+1);setTimeout(ttsPlay,300)}}
function ttsPrev(){if(currentIdx>0){ttsStop();loadChapter(currentIdx-1);setTimeout(ttsPlay,300)}}
function resetBtns(){document.getElementById('btn-play').style.display='inline-block';document.getElementById('btn-pause').style.display='none';document.getElementById('btn-stop').style.display='none'}

// ========== INICIJALIZACIJA ==========
document.addEventListener('keydown',function(e){
    if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;
    if(e.key==='ArrowRight')ttsNext();
    if(e.key==='ArrowLeft')ttsPrev();
    if(e.key===' '){e.preventDefault();if(ttsJob&&!stopFlag)ttsPause();else ttsPlay()}
});
(function(){const fs=localStorage.getItem('fs');if(fs){document.getElementById('font-size').value=fs;document.getElementById('reader-content').style.fontSize=fs+'px'}})();
