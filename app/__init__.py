"""BooklyTTS - EPUB to Audiobook sa Microsoft Edge Neural TTS"""
import os
from flask import Flask
from dotenv import load_dotenv
load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.urandom(24).hex()
    app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_DIR', 'uploads')
    app.config['OUTPUT_FOLDER'] = os.getenv('OUTPUT_DIR', 'output')
    
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        os.makedirs(folder, exist_ok=True)
    
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    return app
