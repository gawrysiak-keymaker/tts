# config.py
import os

# --- TTS Provider Configuration ---
TTS_PROVIDERS = {
    'google': {
        'voices': {
            'en-US-Neural2-F': 'US Female (Neural2 - Premium & Fast)',
            'en-US-Neural2-D': 'US Male (Neural2 - Premium & Fast)',
            'en-US-Wavenet-F': 'US Female (Wavenet - Classic)',
            'en-US-Journey-F': 'US Female (Journey - Ultra Expressive)'
        }
    }
}

# --- Application Settings ---
MAX_CHARS = 50000               
TTS_CHUNK_MAX_BYTES = 4000      

DEFAULT_VOICE = 'en-US-Neural2-F'
LLM_MODEL_TO_USE = "gemini-1.5-flash" 

# --- Local Output Configuration ---
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
GENERATED_OUTPUT_PARENT_DIR = os.path.join(PROJECT_ROOT, "generated_output")