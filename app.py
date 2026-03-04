# app.py
import os
import uuid
import logging
from flask import Flask, render_template, request, jsonify, Response
from google.cloud import texttospeech
from google.oauth2 import service_account
from dotenv import load_dotenv

from config import DEFAULT_VOICE
from tts_utils import liquid_stream_generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

app = Flask(__name__)

# The Vault: Temporarily holds text while the browser connects the audio pipe
stream_vault = {}

# --- Initialize Google Cloud TTS Client ---
google_creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
tts_client = None
if google_creds_path and os.path.isfile(google_creds_path):
    try:
        gcp_creds = service_account.Credentials.from_service_account_file(google_creds_path)
        tts_client = texttospeech.TextToSpeechClient(credentials=gcp_creds)
        logging.info("Google Cloud TTS Client initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize TTS Client: {e}")

@app.route('/')
def index():
    return render_template('index.html', tts_enabled=(tts_client is not None))

@app.route('/prepare_stream', methods=['POST'])
def prepare_stream():
    """Takes the text, gives it a ticket number, and hands the ticket back to the UI."""
    if not tts_client:
        return jsonify({"error": "TTS service unavailable."}), 503

    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({"error": "Invalid text input."}), 400

    # Generate a unique ticket ID for this stream
    stream_id = str(uuid.uuid4())
    stream_vault[stream_id] = text

    # Tell the browser where to connect the audio pipe
    return jsonify({
        "stream_url": f"/stream_audio/{stream_id}"
    })

@app.route('/stream_audio/<stream_id>')
def stream_audio(stream_id):
    """The Browser connects here. We open the valve and pour the Liquid Stream."""
    text = stream_vault.pop(stream_id, None)
    if not text:
        return "Stream not found or expired", 404

    # Response turns our python generator into a live HTTP streaming pipe
    return Response(
        liquid_stream_generator(text, DEFAULT_VOICE, tts_client),
        mimetype="audio/mpeg"
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)