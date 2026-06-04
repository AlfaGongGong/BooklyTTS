"""Audio builder za spajanje chunkova"""
import os
from pydub import AudioSegment

class AudioBuilder:
    def __init__(self, output_dir): self.output_dir = output_dir
    
    def concatenate(self, audio_files, output_path, crossfade_ms=50, add_silence_ms=500):
        if not audio_files: raise ValueError("Nema audio fajlova")
        combined = AudioSegment.from_file(audio_files[0])
        silence = AudioSegment.silent(duration=add_silence_ms)
        for audio_file in audio_files[1:]:
            combined = combined.append(silence, crossfade=0)
            combined = combined.append(AudioSegment.from_file(audio_file), crossfade=crossfade_ms)
        combined.export(output_path, format="mp3", bitrate="192k")
        return output_path
