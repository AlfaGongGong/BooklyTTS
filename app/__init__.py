import os
from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', os.urandom(24).hex())
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['OUTPUT_FOLDER'] = 'output'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
    
    for folder in ['uploads', 'output']:
        os.makedirs(folder, exist_ok=True)
    
    from app.routes import main_bp
    from app.stream_api import stream_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(stream_bp)
    
    return app
