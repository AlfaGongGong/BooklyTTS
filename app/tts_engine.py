"""TTS Engine wrapper za edge-tts (Microsoft Neural)"""
import os
import asyncio

class TTSEngine:
    """Microsoft Edge TTS - najbolji HR/BS glasovi bez modela"""
    
    VOICES = {
        'hr': {
            'female': 'hr-HR-GabrijelaNeural',
            'male': 'hr-HR-SreckoNeural'
        },
        'bs': {
            'male': 'bs-BA-GoranNeural',
            'female': 'bs-BA-VesnaNeural'
        },
        'sr': {
            'male': 'sr-RS-NicholasNeural',
            'female': 'sr-RS-SophieNeural'
        },
        'cs': {
            'male': 'cs-CZ-AntoninNeural',
            'female': 'cs-CZ-VlastaNeural'
        }
    }
    
    def __init__(self, voice='hr-HR-GabrijelaNeural'):
        self.voice = voice
        self.ready = True
    
    def is_ready(self):
        return self.ready
    
    def synthesize(self, text, output_path, voice=None):
        """Sinteza govora koristeci edge-tts"""
        if voice is None:
            voice = self.voice
        
        async def _synthesize():
            import edge_tts
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
        
        asyncio.run(_synthesize())
        return output_path
