import os
import time
import queue
import hashlib
import logging
import threading
from datetime import datetime
from google.cloud import texttospeech
import google.generativeai as genai
import config

# ---------------------------------------------------------------------------
# Thread-Safe TTL Cache (Safe under CPython GIL; use Redis for multi-process)
# ---------------------------------------------------------------------------
class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self.cache = {}
        self.lock = threading.Lock()

    def get(self, key: str):
        with self.lock:
            if key in self.cache:
                val, exp = self.cache[key]
                if time.time() < exp:
                    return val
                del self.cache[key]
            return None

    def set(self, key: str, val: str):
        with self.lock:
            self.cache[key] = (val, time.time() + self.ttl)

# 24-hour TTL Cache for Gemini filenames
gemini_cache = TTLCache(ttl_seconds=86400)

# ---------------------------------------------------------------------------
# Text Chunking
# ---------------------------------------------------------------------------
def split_text_by_bytes(text: str, max_bytes: int = 4000) -> list[str]:
    """
    Splits text safely without breaking UTF-8 characters, preferring 
    paragraphs, sentences, or word boundaries.
    """
    chunks =[]
    while text:
        if len(text.encode('utf-8')) <= max_bytes:
            chunks.append(text)
            break
        
        # Truncate to max_bytes and decode ignoring errors to find a safe string boundary
        truncated_bytes = text.encode('utf-8')[:max_bytes]
        safe_str = truncated_bytes.decode('utf-8', 'ignore')
        
        split_idx = -1
        # Prefer splitting at paragraphs, then sentences, then words
        for sep in['\n\n', '\n', '. ', ', ', ' ']:
            split_idx = safe_str.rfind(sep)
            if split_idx != -1:
                split_idx += len(sep) # Include the separator in the chunk
                break
        
        if split_idx == -1:
            # Force split if no natural boundary is found
            split_idx = len(safe_str)
            
        chunks.append(text[:split_idx])
        text = text[split_idx:].lstrip()
        
    return chunks

# ---------------------------------------------------------------------------
# Background Threads
# ---------------------------------------------------------------------------
def generate_filename_task(text: str, q: queue.Queue, cache: TTLCache):
    """Thread 1 (Namer): Calls Gemini to generate a smart filename."""
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    # Check Cache
    cached_name = cache.get(text_hash)
    if cached_name:
        q.put(cached_name)
        return

    try:
        model_name = config.GEMINI_MODEL_NAME or "gemini-2.0-flash"
        model = genai.GenerativeModel(model_name)
        prompt = (
            "Generate a concise, descriptive filename (max 5 words, snake_case, "
            "no extension, lowercase) for the following text. Return ONLY the filename string.\n\n"
            f"Text: {text[:2000]}"
        )
        response = model.generate_content(prompt)
        name = response.text.strip().replace(' ', '_').replace('\n', '').lower()
        
        # Sanitize filename
        name = ''.join(c for c in name if c.isalnum() or c == '_')
        if not name:
            name = "speech"
            
        cache.set(text_hash, name)
        q.put(name)
    except Exception as e:
        # Log at DEBUG to avoid console noise on 429 Quota errors
        logging.debug(f"Gemini naming failed: {e}")
        q.put("speech")

def save_files_task(audio_data: bytes, text: str, q: queue.Queue):
    """Thread 2 (Scribe): Waits for the name and saves files to disk."""
    try:
        # Wait up to 10 seconds for Gemini to respond
        name = q.get(timeout=10)
    except queue.Empty:
        name = "speech"
        
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    
    folder = os.path.join(config.GENERATED_OUTPUT_PARENT_DIR, date_str)
    os.makedirs(folder, exist_ok=True)
    
    base_filename = f"{date_str.replace('-', '')}_{time_str}_{name}"
    mp3_path = os.path.join(folder, f"{base_filename}.mp3")
    txt_path = os.path.join(folder, f"{base_filename}.txt")
    
    try:
        with open(mp3_path, 'wb') as f:
            f.write(audio_data)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        logging.info(f"Successfully saved files: {base_filename}")
    except Exception as e:
        logging.error(f"Failed to save files: {e}")

# ---------------------------------------------------------------------------
# Streaming Generator
# ---------------------------------------------------------------------------
def stream_and_save_audio(text: str):
    """Generates audio chunks, yields them, and triggers background saving."""
    q = queue.Queue()
    
    # Start Namer Thread immediately
    namer_thread = threading.Thread(
        target=generate_filename_task, 
        args=(text, q, gemini_cache), 
        daemon=True
    )
    namer_thread.start()
    
    client = texttospeech.TextToSpeechClient()
    chunks = split_text_by_bytes(text, config.TTS_CHUNK_MAX_BYTES)
    full_audio = bytearray()
    
    for chunk in chunks:
        if not chunk.strip():
            continue
            
        synthesis_input = texttospeech.SynthesisInput(text=chunk)
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name=config.DEFAULT_VOICE
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        try:
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            audio_content = response.audio_content
            full_audio.extend(audio_content)
            yield audio_content
        except Exception as e:
            logging.error(f"TTS synthesis failed during stream: {e}")
            break # Stop generator gracefully on error
            
    # Start Scribe Thread after all audio is generated
    scribe_thread = threading.Thread(
        target=save_files_task, 
        args=(bytes(full_audio), text, q), 
        daemon=True
    )
    scribe_thread.start()