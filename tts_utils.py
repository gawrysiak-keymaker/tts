# tts_utils.py
import os
import re
from google.cloud import texttospeech
from config import TTS_CHUNK_MAX_BYTES

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
            sent_breaks =[m.end() for m in re.finditer(b'[.?!](?=\s|\Z)', search_segment)]
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

def liquid_stream_generator(text: str, voice_name: str, tts_client):
    """
    THE LIQUID STREAM:
    Sends text chunks to Google sequentially. The exact millisecond Google 
    returns a chunk of MP3 bytes, it yields them directly into the browser's audio pipe.
    """
    chunks = split_text_by_bytes(text)
    if not chunks:
        return

    lang_code = "-".join(voice_name.split("-")[:2])
    
    for chunk_text in chunks:
        if not chunk_text.strip(): continue
        
        synthesis_input = texttospeech.SynthesisInput(text=chunk_text)
        voice_params = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
        
        # We ask Google for the audio...
        response = tts_client.synthesize_speech(
            request={"input": synthesis_input, "voice": voice_params, "audio_config": audio_config}
        )
        
        # Instantly stream the raw MP3 bytes down the pipe!
        yield response.audio_content