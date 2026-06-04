import os, subprocess

class AudioBuilder:
    def __init__(self, output_dir='output'):
        os.makedirs(output_dir, exist_ok=True)
    
    def concatenate(self, audio_files, output_path):
        if not audio_files: raise ValueError("Nema audio fajlova")
        
        # O-03: Koristi stream copy za brzinu (bez re-enkodiranja)
        concat_file = output_path + '.concat.txt'
        with open(concat_file, 'w') as f:
            for af in audio_files:
                f.write(f"file '{os.path.abspath(af)}'\n")
        
        subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
                      '-i', concat_file, '-c:a', 'copy', output_path],
                     check=True, capture_output=True)
        os.remove(concat_file)
        return output_path
