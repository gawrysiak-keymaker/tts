# config.py
import os

# --- TTS Provider Configuration ---
TTS_PROVIDERS = {
    'google': {
        'voices': {
            'en-US-Wavenet-F': 'US Female (Wavenet - Classic Speed)'
        }
    }
}

# --- Application Settings ---
MAX_CHARS = 50000               
TTS_CHUNK_MAX_BYTES = 4000      
DEFAULT_VOICE = 'en-US-Wavenet-F'

# --- Local Output Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATED_OUTPUT_PARENT_DIR = os.path.join(PROJECT_ROOT, "generated_output")