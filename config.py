import os

# Application Constants
MAX_CHARS = 50000
TTS_CHUNK_MAX_BYTES = 4000
DEFAULT_VOICE = 'en-US-Wavenet-F'

# Output Directory (OS-agnostic)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GENERATED_OUTPUT_PARENT_DIR = os.path.join(BASE_DIR, 'generated_output')

# Hardcode the precise, fast, cheap Gemini 3.1 model
GEMINI_MODEL_NAME = "gemini-3.1-flash-lite-preview"