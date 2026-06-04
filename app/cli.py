#!/usr/bin/env python3
import os, sys, asyncio, click
from rich.console import Console
from rich.progress import Progress

console = Console()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.tts_engine import TTSEngine
from app.epub_processor import EPUBProcessor
from app.audio_builder import AudioBuilder

engine = TTSEngine()
epub_processor = EPUBProcessor()
builder = AudioBuilder(output_dir='output')

@click.command()
@click.option('--epub', 'epub_path', help='EPUB fajl')
@click.option('--voice', default='hr-HR-GabrijelaNeural', help='Glas')
@click.option('--output', help='Izlazni fajl')
def cli(epub_path, voice, output):
    if not epub_path:
        console.print("[red]Navedi --epub[/red]")
        return
    
    chapters = epub_processor.extract_chapters(epub_path)
    console.print(f"[green]{len(chapters)} poglavlja[/green]")
    
    audio_files = []
    for i, ch in enumerate(chapters):
        if len(ch['text'].strip()) < 50: continue
        out = f"output/ch_{i:04d}.mp3"
        engine.synthesize(ch['text'], out, voice=voice)
        audio_files.append(out)
        console.print(f"  [{i+1}/{len(chapters)}] {ch['title'][:40]}...")
    
    output_path = output or f"audiobook_{os.path.basename(epub_path).replace('.epub','')}.mp3"
    builder.concatenate(audio_files, output_path)
    console.print(f"[green bold]OK: {output_path}[/green bold]")
    
    for f in audio_files:
        try: os.remove(f)
        except: pass

if __name__ == '__main__':
    cli()
