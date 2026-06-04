"""Podrška za više TTS engine-a"""
import os, asyncio, tempfile, subprocess

class MultiTTS:
    ENGINES = {
        'edge': {'name': 'Microsoft Edge', 'online': True, 'free': True, 'quality': 4},
        'google': {'name': 'Google Cloud Neural2', 'online': True, 'free': '1M char/mj', 'quality': 5},
        'elevenlabs': {'name': 'ElevenLabs', 'online': True, 'free': '10k char', 'quality': 5},
        'rhvoice': {'name': 'RHVoice (offline)', 'online': False, 'free': True, 'quality': 3},
        'espeak': {'name': 'eSpeak-NG (offline)', 'online': False, 'free': True, 'quality': 1},
    }
    
    # Google Neural2 glasovi za HR/BS/SR
    GOOGLE_VOICES = {
        'hr-HR': {
            'female': 'hr-HR-Standard-A',  # Standard (besplatan)
            'female_neural': 'hr-HR-Chirp3-HD-F',  # Neural2 (bolji, ali košta)
        },
        'sr-RS': {
            'female': 'sr-RS-Standard-A',
            'female_neural': 'sr-RS-Chirp3-HD-F',
        }
    }
    
    @staticmethod
    def list_engines():
        return MultiTTS.ENGINES
    
    @staticmethod
    def synthesize(text, engine='edge', voice='hr-HR-GabrijelaNeural', output_path=None):
        if output_path is None:
            output_path = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False).name
        
        if engine == 'edge':
            return MultiTTS._edge(text, voice, output_path)
        elif engine == 'google':
            return MultiTTS._google_cloud(text, voice, output_path)
        elif engine == 'elevenlabs':
            return MultiTTS._elevenlabs(text, voice, output_path)
        elif engine == 'rhvoice':
            return MultiTTS._rhvoice(text, output_path)
        elif engine == 'espeak':
            return MultiTTS._espeak(text, output_path)
        
        return output_path
    
    @staticmethod
    def _edge(text, voice, output_path):
        async def _run():
            import edge_tts
            comm = edge_tts.Communicate(text, voice)
            await comm.save(output_path)
        asyncio.run(_run())
        return output_path
    
    @staticmethod
    def _google_cloud(text, voice, output_path):
        """Google Cloud TTS sa Neural2 podrškom"""
        try:
            from google.cloud import texttospeech
            
            client = texttospeech.TextToSpeechClient()
            
            # Parsiraj voice name (npr. "hr-HR-Chirp3-HD-F")
            language_code = "-".join(voice.split("-")[:2])  # hr-HR
            
            synthesis_input = texttospeech.SynthesisInput(text=text[:5000])
            
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice
            )
            
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                speaking_rate=1.0
            )
            
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
            
            with open(output_path, 'wb') as f:
                f.write(response.audio_content)
                
        except Exception as e:
            # Fallback: koristi gTTS (besplatni Google TTS)
            print(f"Google Cloud TTS nije dostupan: {e}, koristim gTTS")
            try:
                from gtts import gTTS
                tts = gTTS(text=text[:5000], lang='hr')
                tts.save(output_path)
            except:
                return MultiTTS._edge(text, 'hr-HR-GabrijelaNeural', output_path)
        
        return output_path
    
    @staticmethod
    def _elevenlabs(text, voice, output_path):
        api_key = os.getenv('ELEVENLABS_API_KEY', '')
        if not api_key:
            raise Exception("ELEVENLABS_API_KEY nije postavljen")
        
        import requests
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
        data = {"text": text[:5000], "model_id": "eleven_multilingual_v2"}
        
        resp = requests.post(url, json=data, headers=headers)
        if resp.status_code == 200:
            with open(output_path, 'wb') as f:
                f.write(resp.content)
        return output_path
    
    @staticmethod
    def _rhvoice(text, output_path):
        wav_path = output_path.replace('.mp3', '.wav')
        try:
            subprocess.run(['rhvoice-client', '-v', 'andrej', '-o', wav_path],
                         input=text.encode(), capture_output=True, timeout=30)
            if os.path.exists(wav_path):
                subprocess.run(['ffmpeg', '-y', '-i', wav_path, '-c:a', 'libmp3lame', output_path],
                             capture_output=True)
                os.remove(wav_path)
        except: pass
        return output_path
    
    @staticmethod
    def _espeak(text, output_path):
        try:
            subprocess.run(['espeak-ng', '-v', 'hr', '-w', output_path, text],
                         capture_output=True, timeout=30)
        except: pass
        return output_path
