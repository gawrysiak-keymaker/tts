# tts_utils.py
import os
import tempfile
import logging
import re
from datetime import datetime
import concurrent.futures

from google.cloud import texttospeech
from pydub import AudioSegment
from config import TTS_CHUNK_MAX_BYTES, GENERATED_OUTPUT_PARENT_DIR

def clean_filename(text: str) -> str:
    """Cleans the Gemini response into a safe folder name."""
    if not text: return "untitled"
    cleaned = re.sub(r'[^\w\s-]', '', text).strip().lower()
    cleaned = re.sub(r'[\s_]+', '_', cleaned)
    return cleaned[:50] or "untitled"

def suggest_filename_llm(text_sample: str, llm_model_instance) -> str:
    """The Gemini Shadow Clone: Asks for a filename."""
    if not llm_model_instance:
        return "speech"
    try:
        prompt_text = text_sample[:600]
        prompt = f"Suggest a very concise, descriptive filename base (3-5 words max, underscores_for_spaces, lowercase, alphanumeric_only) for this text: '{prompt_text}'"
        
        response = llm_model_instance.generate_content(prompt)
        if response and response.text:
            return clean_filename(response.text)
        return "speech"
    except Exception as e:
        logging.error(f"Gemini LLM Error: {e}")
        return "speech"

def split_text_by_bytes(text: str, max_bytes: int = 4000, encoding: str = 'utf-8') -> list[str]:
    """Safely chunks text to respect Google's payload limits."""
    chunks =[]
    text_bytes = text.encode(encoding)
    text_len_bytes = len(text_bytes)
    current_chunk_start = 0

    while current_chunk_start < text_len_bytes:
        end_byte_limit = min(current_chunk_start + max_bytes, text_len_bytes)
        if end_byte_limit >= text_len_bytes:
            actual_end_byte = text_len_bytes
        else:
            actual_end_byte = end_byte_limit
            while actual_end_byte > current_chunk_start and (text_bytes[actual_end_byte] & 0xC0) == 0x80:
                actual_end_byte -= 1
            search_segment = text_bytes[current_chunk_start:actual_end_byte]
            para_breaks =[m.end() for m in re.finditer(b'\n\s*\n', search_segment)]
            sent_breaks = [m.end() for m in re.finditer(b'[.?!](?=\s|\Z)', search_segment)]
            space_breaks =[m.end() for m in re.finditer(b'\s', search_segment)]
            best_break = max(para_breaks or sent_breaks or space_breaks or [0])
            if best_break > 0: actual_end_byte = current_chunk_start + best_break
        
        if actual_end_byte == current_chunk_start:
            actual_end_byte = end_byte_limit
            
        chunk_bytes = text_bytes[current_chunk_start:actual_end_byte]
        decoded_chunk = chunk_bytes.decode(encoding, errors='ignore').strip()
        if decoded_chunk: chunks.append(decoded_chunk)
        current_chunk_start = actual_end_byte
        
    return chunks

def _generate_with_google(text: str, voice_name: str, tts_client_instance) -> bytes:
    """The Main Worker: Handles the TTS generation with Google."""
    chunks = split_text_by_bytes(text)
    if not chunks:
        raise ValueError("Input text is empty.")

    lang_code = "-".join(voice_name.split("-")[:2])
    combined_audio = AudioSegment.empty()
    
    with tempfile.TemporaryDirectory() as temp_dir:
        for i, chunk_text in enumerate(chunks):
            if not chunk_text.strip(): continue
            chunk_path = os.path.join(temp_dir, f"chunk_{i}.mp3")
            synthesis_input = texttospeech.SynthesisInput(text=chunk_text)
            voice_params = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            
            response = tts_client_instance.synthesize_speech(
                request={"input": synthesis_input, "voice": voice_params, "audio_config": audio_config}
            )
            with open(chunk_path, "wb") as out:
                out.write(response.audio_content)
            
            combined_audio += AudioSegment.from_mp3(chunk_path)

    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as temp_f:
        combined_audio.export(temp_f.name, format="mp3")
        return temp_f.read()

def process_tts_and_naming_parallel(text: str, voice_name: str, tts_client, llm_model):
    """Executes TTS and Gemini naming at the exact same time."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # --- DUAL CAST: Launch 2 workers simultaneously ---
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_audio = executor.submit(_generate_with_google, text, voice_name, tts_client)
        future_name = executor.submit(suggest_filename_llm, text, llm_model)
        
        # Wait for both workers to return their loot
        audio_bytes = future_audio.result()
        smart_name = future_name.result()
    # --------------------------------------------------

    final_basename = f"{timestamp}_{smart_name}"
    output_dir = os.path.join(GENERATED_OUTPUT_PARENT_DIR, final_basename)
    os.makedirs(output_dir, exist_ok=True)

    mp3_path = os.path.join(output_dir, f"{final_basename}.mp3")
    with open(mp3_path, 'wb') as f:
        f.write(audio_bytes)

    txt_path = os.path.join(output_dir, f"{final_basename}.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)

    return mp3_path, txt_path, output_dir, final_basename