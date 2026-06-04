import os, asyncio, tempfile, re

class TTSEngine:
    VOICES = {
        'hr': {'female': 'hr-HR-GabrijelaNeural', 'male': 'hr-HR-SreckoNeural'},
        'bs': {'male': 'bs-BA-GoranNeural', 'female': 'bs-BA-VesnaNeural'},
        'sr': {'male': 'sr-RS-NicholasNeural', 'female': 'sr-RS-SophieNeural'}
    }
    
    def __init__(self, voice='hr-HR-GabrijelaNeural'):
        self.voice = voice
        self.ready = True
    
    def is_ready(self): return self.ready
    
    def _chunk_text(self, text, max_chars=3000):
        """Podijeli tekst na chunkove po rečenicama, max 3000 char"""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks, current = [], ""
        for s in sentences:
            if len(current) + len(s) > max_chars:
                if current: chunks.append(current.strip())
                current = s
            else:
                current += " " + s if current else s
        if current: chunks.append(current.strip())
        return chunks or [text]
    
    def synthesize(self, text, output_path, voice=None):
        if voice is None: voice = self.voice
        
        chunks = self._chunk_text(text)
        
        async def _synthesize_all():
            import edge_tts
            # Sinteza svih chunkova sekvencijalno (da ne preoptereti API)
            chunk_files = []
            for i, chunk in enumerate(chunks):
                tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                communicate = edge_tts.Communicate(chunk, voice)
                await communicate.save(tmp.name)
                chunk_files.append(tmp.name)
            
            # Spoji sve chunkove
            if len(chunk_files) == 1:
                os.rename(chunk_files[0], output_path)
            else:
                with open(output_path, 'wb') as out:
                    for cf in chunk_files:
                        with open(cf, 'rb') as inf:
                            out.write(inf.read())
                        os.remove(cf)
        
        asyncio.run(_synthesize_all())
        return output_path
    
    def stream_chapter(self, text, voice=None, max_chars=3000):
        if voice is None: voice = self.voice
        text = text[:max_chars]
        tmpfile = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        self.synthesize(text, tmpfile.name, voice)
        return tmpfile.name
