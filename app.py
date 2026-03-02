# app.py
import os
import logging
from flask import Flask, render_template, request, send_from_directory, jsonify
from google.cloud import texttospeech
from google.oauth2 import service_account
import google.generativeai as genai
from dotenv import load_dotenv

from config import TTS_PROVIDERS, MAX_CHARS, DEFAULT_VOICE, GENERATED_OUTPUT_PARENT_DIR, LLM_MODEL_TO_USE
from tts_utils import process_tts_and_naming_parallel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

app = Flask(__name__)

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

# --- Initialize Gemini LLM Client ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
llm_model = None
if GOOGLE_API_KEY:
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        llm_model = genai.GenerativeModel(LLM_MODEL_TO_USE)
        logging.info(f"Gemini LLM initialized successfully ({LLM_MODEL_TO_USE}).")
    except Exception as e:
        logging.error(f"Failed to initialize Gemini LLM: {e}")

@app.route('/')
def index():
    """Renders the Tailwind UI."""
    flat_voices = {v_id: v_desc for provider in TTS_PROVIDERS.values() for v_id, v_desc in provider.get('voices', {}).items()}
    return render_template('index.html', allowed_voices=flat_voices, max_chars=MAX_CHARS, tts_enabled=(tts_client is not None), DEFAULT_VOICE=DEFAULT_VOICE)

@app.route('/convert', methods=['POST'])
def convert():
    """Handles TTS generation and LLM naming in parallel."""
    if not tts_client:
         return jsonify({"error": "TTS service unavailable."}), 503

    text = request.form.get('text', '').strip()
    voice = request.form.get('selected_voice', '').strip()

    if not text or len(text) > MAX_CHARS:
        return jsonify({"error": "Invalid text input."}), 400

    try:
        # Call the new Parallel function
        mp3_path, txt_path, output_dir, basename = process_tts_and_naming_parallel(text, voice, tts_client, llm_model)
        
        audio_url = f"/serve_audio/{basename}/{basename}.mp3"

        return jsonify({
            "message": "Success!",
            "local_output_directory": output_dir,
            "audio_url_mp3_player": audio_url,
            "filename_base": basename
        })

    except Exception as e:
        logging.exception("Error during conversion:")
        return jsonify({"error": str(e)}), 500

@app.route('/serve_audio/<folder>/<filename>')
def serve_audio(folder, filename):
    """Serves the generated audio file securely from the local folder."""
    safe_dir = os.path.join(GENERATED_OUTPUT_PARENT_DIR, folder)
    return send_from_directory(safe_dir, filename, mimetype='audio/mpeg')

if __name__ == '__main__':
    os.makedirs(GENERATED_OUTPUT_PARENT_DIR, exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5001)