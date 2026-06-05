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

    def synthesize(self, text, output_path, voice=None, epub_name=None, loop=None):
        """
        Sintetizira tekst u MP3 na output_path.

        ARCH-05: epub_name se prosljeđuje replaceru za per-book pravila.
        ARCH-03: prihvaća postojeći event loop (iz stream workera) da izbjegne
                 50x kreiranje/destrukciju loopa po jobu.
        ARCH-04: ffmpeg greška se eksplicitno detektira i baca RuntimeError.
        """
        if voice is None:
            voice = self.voice

        # ARCH-05: per-book zamjene ako je epub_name dostupan
        text = self.replacer.apply(text, epub_name=epub_name)
        chunks = self._chunk_text(text)

        async def _synth_all():
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

                # ARCH-04: eksplicitna provjera ffmpeg rezultata
                result = subprocess.run([
                    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                    '-i', concat, '-c:a', 'copy', output_path
                ], check=False, capture_output=True)

                os.remove(concat)
                for fp in files:
                    try:
                        os.remove(fp)
                    except OSError:
                        pass

                if result.returncode != 0 or not os.path.exists(output_path):
                    raise RuntimeError(
                        f"ffmpeg greška (returncode={result.returncode}): "
                        f"{result.stderr.decode(errors='replace')[:300]}"
                    )

        # ARCH-03: koristi proslijeđeni loop ako postoji, inače kreira novi
        if loop is not None:
            loop.run_until_complete(_synth_all())
        else:
            asyncio.run(_synth_all())

        return output_path

    def stream_chapter(self, text, voice=None, epub_name=None, max_chars=3000):
        if voice is None:
            voice = self.voice
        # ARCH-05: prosljeđuj epub_name i ovdje
        text_to_synth = self.replacer.apply(text[:max_chars], epub_name=epub_name)
        tmpfile = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
        self.synthesize(text_to_synth, tmpfile.name, voice, epub_name=epub_name)
        return tmpfile.name
