import os
import google.generativeai as genai

# Application Constants
MAX_CHARS = 50000
TTS_CHUNK_MAX_BYTES = 4000
DEFAULT_VOICE = 'en-US-Wavenet-F'

# Output Directory (OS-agnostic)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_OUTPUT_PARENT_DIR = os.path.join(BASE_DIR, 'generated_output')

# This will be set dynamically in app.py
GEMINI_MODEL_NAME = None

def get_available_flash_lite_model(api_key: str) -> str:
    """
    Dynamically picks a Gemini model containing 'flash-lite'.
    Falls back to 'gemini-2.0-flash' if none is found or on error.
    """
    fallback_model = "gemini-2.0-flash"
    if not api_key:
        return fallback_model
        
    try:
        genai.configure(api_key=api_key)
        models = genai.list_models()
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                if 'flash-lite' in m.name.lower():
                    return m.name
        return fallback_model
    except Exception:
        return fallback_model