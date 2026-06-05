let allChapters=[],currentIdx=0,epubFile=null,ttsJob=null,stopFlag=false,rate=1.0,paused=false,audio=null;
let timeStart=0,timeInterval=null,preloadQueue=[];

// Detektuj mobilni
const isMobile=window.innerWidth<768;
if(isMobile){
    document.getElementById('sidebar-toggle-btn').style.display='inline-block';
    document.querySelectorAll('.sidebar-close-btn').forEach(b=>b.style.display='inline-block');
}

// UPLOAD
document.getElementById('epub-file').addEventListener('change',async function(){
    const f=this.files[0];if(!f)return;
    document.getElementById('upload-status').textContent='⏳...';
    const fd=new FormData();fd.append('epub_file',f);
    try{
        const r=await fetch('/upload-epub',{method:'POST',body:fd});const d=await r.json();
        if(d.success){
            epubFile=d.filename;allChapters=d.chapters;
            document.getElementById('book-title').textContent=d.metadata.title;
            document.getElementById('upload-status').textContent='✅ '+d.chapter_count+' pogl.';
            document.querySelector('.welcome').style.display='none';
            renderChapters();loadChapter(0);
        }else{document.getElementById('upload-status').textContent='❌ '+d.error}
    }catch(e){document.getElementById('upload-status').textContent='❌ Greška'}
});

function renderChapters(){
    document.getElementById('chapter-list').innerHTML=allChapters.map((c,i)=>
        `<div class="chapter-item${i===currentIdx?' active':''}" onclick="loadChapter(${i});if(isMobile)closeSidebar()" id="ch-${i}">${i+1}. ${c.title||'Pogl.'+(i+1)}</div>`).join('');
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
    const a=document.getElementById('ch-'+i);if(a)a.classList.add('active');
}
function prevPage(){document.getElementById('reader-content').scrollBy({top:-400,behavior:'smooth'})}
function nextPage(){document.getElementById('reader-content').scrollBy({top:400,behavior:'smooth'})}
function toggleSidebar(){
    const s=document.getElementById('sidebar'),o=document.getElementById('sidebar-overlay');
    s.classList.toggle('open');o.classList.toggle('active');
}
function closeSidebar(){
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('sidebar-overlay').classList.remove('active');
}
function changeFontSize(s){document.getElementById('reader-content').style.fontSize=s+'px';localStorage.setItem('fs',s)}
function toggleTheme(){const b=document.body;b.style.background=b.style.background==='#fff'?'#0d1117':'#fff';b.style.color=b.style.color==='#24292f'?'#e6edf3':'#24292f'}
function updateRate(v){rate=parseFloat(v);document.getElementById('rate-val').textContent=v+'x';if(audio)audio.playbackRate=rate}
function toggleTTS(){const b=document.getElementById('tts-bar');b.style.display=b.style.display==='block'?'none':'block'}

async function searchSentence(){
    const q=document.getElementById('sentence-search').value.trim();if(!q)return;
    document.getElementById('search-result').textContent='🔍...';
    try{
        const r=await fetch('/find-sentence',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({sentence:q,epub_filename:epubFile})});
        const d=await r.json();
        document.getElementById('search-result').textContent=d.found?'✅ Pogl.'+(d.chapter_idx+1):'❌ Nije pronađeno';
        if(d.found)loadChapter(d.chapter_idx);
    }catch(e){document.getElementById('search-result').textContent='❌ Greška'}
}

function startTimer(){timeStart=Date.now();timeInterval=setInterval(()=>{const e=Math.floor((Date.now()-timeStart)/1000);document.getElementById('info-time').textContent=`${Math.floor(e/60)}:${String(e%60).padStart(2,'0')}`},1000)}
function stopTimer(){if(timeInterval){clearInterval(timeInterval);timeInterval=null}}

async function ttsPlay(){
    if(!allChapters.length){alert('Uploaduj EPUB!');return}
    stopFlag=false;paused=false;preloadQueue=[];
    document.getElementById('btn-play').style.display='none';
    document.getElementById('btn-pause').style.display='inline-block';
    document.getElementById('btn-stop').style.display='inline-block';
    document.getElementById('info-chapter').textContent='Pogl: '+(currentIdx+1)+'/'+allChapters.length;
    startTimer();
    try{
        const r=await fetch('/stream-start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({chapter:currentIdx,voice:document.getElementById('tts-voice').value,epub_filename:epubFile})});
        const d=await r.json();
        if(d.job_id){ttsJob=d.job_id;preloadAndPlay()}
        else{resetBtns();stopTimer()}
    }catch(e){resetBtns();stopTimer()}
}

async function preloadAndPlay(){
    if(stopFlag||!ttsJob)return;
    for(let i=0;i<3;i++){if(stopFlag)return;
        try{
            const r=await fetch('/stream-next/'+ttsJob);const ct=r.headers.get('content-type')||'';
            if(ct.includes('audio')){
                const blob=await r.blob();
                preloadQueue.push({url:URL.createObjectURL(blob),ch:parseInt(r.headers.get('X-Ch')||currentIdx),ck:parseInt(r.headers.get('X-Ck')||0)+1,ckTot:parseInt(r.headers.get('X-CkTot')||1),chTot:parseInt(r.headers.get('X-ChTot')||allChapters.length)});
            }else{const d=await r.json();if(d.finished){preloadQueue.push({done:true});break}}
        }catch(e){break}
    }
    if(preloadQueue.length>0)playFromQueue(0);
}
function playFromQueue(idx){
    if(stopFlag||idx>=preloadQueue.length)return;
    const item=preloadQueue[idx];
    if(item.done){resetBtns();stopTimer();if(currentIdx<allChapters.length-1)setTimeout(()=>{ttsStop();loadChapter(currentIdx+1);setTimeout(ttsPlay,500)},2000);return}
    if(audio){audio.pause();audio.src='';audio.load();audio=null}
    audio=new Audio(item.url);audio.playbackRate=rate;audio.play();
    document.getElementById('info-chapter').textContent=`Pogl: ${item.ch+1}/${item.chTot}`;
    document.getElementById('info-chunk').textContent=`Chunk: ${item.ck}/${item.ckTot}`;
    audio.onended=()=>{if(!stopFlag&&!paused){if(idx===preloadQueue.length-2)loadMoreChunks();playFromQueue(idx+1)}};
    if(idx===0)setTimeout(loadMoreChunks,1000);
}
async function loadMoreChunks(){
    if(stopFlag||!ttsJob)return;
    for(let i=0;i<2;i++){if(stopFlag)return;
        try{
            const r=await fetch('/stream-next/'+ttsJob);const ct=r.headers.get('content-type')||'';
            if(ct.includes('audio')){
                const blob=await r.blob();
                preloadQueue.push({url:URL.createObjectURL(blob),ch:parseInt(r.headers.get('X-Ch')||currentIdx),ck:parseInt(r.headers.get('X-Ck')||0)+1,ckTot:parseInt(r.headers.get('X-CkTot')||1),chTot:parseInt(r.headers.get('X-ChTot')||allChapters.length)});
            }else{const d=await r.json();if(d.finished){preloadQueue.push({done:true});return}}
        }catch(e){return}
    }
}
function ttsPause(){
    if(!audio)return;
    if(paused){audio.play();paused=false;document.getElementById('btn-pause').textContent='⏸️';startTimer()}
    else{audio.pause();paused=true;document.getElementById('btn-pause').textContent='▶️';stopTimer()}
}
function ttsStop(){stopFlag=true;ttsJob=null;if(audio){audio.pause();audio.src='';audio.load();audio=null}preloadQueue.forEach(p=>{if(p.url)URL.revokeObjectURL(p.url)});preloadQueue=[];resetBtns();stopTimer()}
function ttsNext(){if(currentIdx<allChapters.length-1){ttsStop();loadChapter(currentIdx+1);setTimeout(ttsPlay,300)}}
function ttsPrev(){if(currentIdx>0){ttsStop();loadChapter(currentIdx-1);setTimeout(ttsPlay,300)}}
function resetBtns(){document.getElementById('btn-play').style.display='inline-block';document.getElementById('btn-pause').style.display='none';document.getElementById('btn-stop').style.display='none'}

document.addEventListener('keydown',function(e){
    if(e.target.tagName==='INPUT'||e.target.tagName==='TEXTAREA')return;
    if(e.key==='ArrowRight')ttsNext();if(e.key==='ArrowLeft')ttsPrev();
    if(e.key===' '){e.preventDefault();if(ttsJob&&!stopFlag)ttsPause();else ttsPlay()}
});
(function(){const fs=localStorage.getItem('fs');if(fs){document.getElementById('font-size').value=fs;document.getElementById('reader-content').style.fontSize=fs+'px'}})();
