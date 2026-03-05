import os
import time
import uuid
import logging
from flask import Flask, request, jsonify, render_template, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

import config
from tts_utils import stream_and_save_audio

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

# Configure Logging
logging.basicConfig(level=logging.INFO if not app.config['DEBUG'] else logging.DEBUG)

# Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Initialize Gemini Model
api_key = os.getenv("GEMINI_API_KEY")
config.GEMINI_MODEL_NAME = config.get_available_flash_lite_model(api_key)
app.logger.info(f"Selected Gemini Model: {config.GEMINI_MODEL_NAME}")

# ---------------------------------------------------------------------------
# Stream Vault (Thread-safe under GIL; replace with Redis for multi-process)
# ---------------------------------------------------------------------------
vault = {}
VAULT_TTL = 300  # 5 minutes

def cleanup_vault():
    """Removes expired entries from the stream vault."""
    now = time.time()
    expired_keys =[k for k, v in vault.items() if now - v['timestamp'] > VAULT_TTL]
    for k in expired_keys:
        del vault[k]

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/prepare_stream', methods=['POST'])
@limiter.limit("10 per minute")
def prepare_stream():
    cleanup_vault()
    
    data = request.json or {}
    text = data.get('text', '').strip()
    
    if not text:
        return jsonify({"error": "Text is required"}), 400
        
    if len(text) > config.MAX_CHARS:
        return jsonify({"error": f"Text exceeds maximum length of {config.MAX_CHARS} characters"}), 413
        
    stream_id = str(uuid.uuid4())
    vault[stream_id] = {
        'text': text,
        'timestamp': time.time()
    }
    
    return jsonify({"stream_url": f"/stream_audio/{stream_id}"})

@app.route('/stream_audio/<stream_id>')
def stream_audio(stream_id):
    if stream_id not in vault:
        return "Stream not found or expired", 404
        
    # Retrieve and immediately remove the text from the vault
    text = vault.pop(stream_id)['text']
    
    return Response(
        stream_and_save_audio(text), 
        mimetype="audio/mpeg"
    )

if __name__ == '__main__':
    app.run(port=5000, threaded=True)