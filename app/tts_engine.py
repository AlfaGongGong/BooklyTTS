import os
import asyncio
import tempfile
import re
import subprocess
from app.replacer import NameReplacer


class TTSEngine:
    VOICES = {
        'hr': {'female': 'hr-HR-GabrijelaNeural', 'male': 'hr-HR-SreckoNeural'},
        'bs': {'male': 'bs-BA-GoranNeural', 'female': 'bs-BA-VesnaNeural'},
        'sr': {'male': 'sr-RS-NicholasNeural', 'female': 'sr-RS-SophieNeural'}
    }

    def __init__(self, voice='hr-HR-GabrijelaNeural'):
        self.voice = voice
        self.ready = True
        self.replacer = NameReplacer()

    def is_ready(self):
        return self.ready

    def _chunk_text(self, text, max_chars=3000):
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = ""
        for s in sentences:
            if len(current) + len(s) > max_chars:
                if current:
                    chunks.append(current.strip())
                current = s
            else:
                current += " " + s if current else s
        if current:
            chunks.append(current.strip())
        return chunks or [text]

    def synthesize(self, text, output_path, voice=None):
        if voice is None:
            voice = self.voice
        text = self.replacer.apply(text)
        chunks = self._chunk_text(text)

        async def _synth():
            import edge_tts
            files = []
            for chunk in chunks:
                tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
                await edge_tts.Communicate(chunk, voice).save(tmp.name)
                files.append(tmp.name)

            if len(files) == 1:
                os.rename(files[0], output_path)
            else:
                concat = output_path + '.txt'
                with open(concat, 'w', encoding='utf-8') as f:
                    for fp in files:
                        f.write(f"file '{os.path.abspath(fp)}'\n")
                subprocess.run([
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', concat, '-c:a', 'copy', output_path
                ], check=False, capture_output=True)
                os.remove(concat)
                for fp in files:
                    os.remove(fp)

        asyncio.run(_synth())
        return output_path

    def stream_chapter(self, text, voice=None, max_chars=3000):
        if voice is None:
            voice = self.voice
        text = self.replacer.apply(text[:max_chars])
        tmpfile = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        self.synthesize(text, tmpfile.name, voice)
        return tmpfile.name
