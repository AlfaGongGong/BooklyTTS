"""Audio builder koristeci ffmpeg"""
import os, subprocess

class AudioBuilder:
    def __init__(self, output_dir='output'):
        os.makedirs(output_dir, exist_ok=True)
    
    def concatenate(self, audio_files, output_path, crossfade_ms=50):
        if not audio_files:
            raise ValueError("Nema audio fajlova")
        
        concat_file = output_path + '.concat.txt'
        with open(concat_file, 'w') as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        
        subprocess.run([
            'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
            '-i', concat_file, '-c:a', 'libmp3lame', '-b:a', '192k', output_path
        ], check=True, capture_output=True)
        
        os.remove(concat_file)
        
        size_mb = os.path.getsize(output_path) / (1024*1024)
        print(f"[AudioBuilder] {output_path} ({size_mb:.1f} MB)")
        return output_path
