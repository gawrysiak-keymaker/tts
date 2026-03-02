# tts_utils.py
# Core TTS logic, local saving, and utilities.

import os
import tempfile
import shutil
import time
import logging
import re
from datetime import datetime

# External Libraries
from google.cloud import texttospeech
from google.api_core.exceptions import GoogleAPIError, InvalidArgument
import google.generativeai as genai
from pydub import AudioSegment
import elevenlabs
from elevenlabs import VoiceSettings

# Import necessary configuration
from config import TTS_CHUNK_MAX_BYTES, GENERATED_OUTPUT_PARENT_DIR

# ======== FILENAME CLEANING FUNCTION ========
def clean_filename(text: str) -> str:
    """
    Cleans a string to make it a safe and valid base for a filename.
    """
    if not text: return "untitled"
    cleaned = text.replace('"', '').replace("'", "")
    cleaned = re.sub(r'[<>:"/\\|?*.,!@#$%^&()+={}[\];`~]', '_', cleaned)
    cleaned = re.sub(r'\s+', '_', cleaned)
    cleaned = re.sub(r'[^\w-]+', '', cleaned)
    cleaned = re.sub(r'[-_]{2,}', '_', cleaned)
    cleaned = cleaned.strip('_.-')
    if not cleaned or cleaned in {".", ".."} or re.fullmatch(r'[-_]+', cleaned):
        cleaned = "untitled"
    return cleaned.lower()[:50]

# ======== BYTE-SAFE CHUNKING FUNCTION (for Google) ========
# FIX: Hard-cap max_bytes at 4000. Google's absolute limit is 5000 bytes. 
# Lowering this strictly to 4000 prevents 500 Internal Errors when text 
# contains multi-byte characters (emojis, accented characters).
def split_text_by_bytes(text: str, max_bytes: int = 4000, encoding: str = 'utf-8') -> list[str]:
    """
    Splits text into chunks that do not exceed a maximum byte size, ensuring
    that multi-byte characters are not split. It prioritizes splitting at
    natural boundaries like paragraphs, sentences, or spaces.
    """
    # Enforce safe upper limit regardless of config imports
    if max_bytes > 4000:
        max_bytes = 4000

    chunks = []
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
            para_breaks = [m.end() for m in re.finditer(b'\n\s*\n', search_segment)]
            sent_breaks = [m.end() for m in re.finditer(b'[.?!](?=\s|\Z)', search_segment)]
            space_breaks = [m.end() for m in re.finditer(b'\s', search_segment)]
            best_break = 0
            if para_breaks: best_break = max(para_breaks)
            elif sent_breaks: best_break = max(sent_breaks)
            elif space_breaks: best_break = max(space_breaks)
            if best_break > 0: actual_end_byte = current_chunk_start + best_break
        if actual_end_byte == current_chunk_start:
            actual_end_byte = end_byte_limit
        chunk_bytes = text_bytes[current_chunk_start:actual_end_byte]
        decoded_chunk = chunk_bytes.decode(encoding, errors='ignore').strip()
        if decoded_chunk: chunks.append(decoded_chunk)
        current_chunk_start = actual_end_byte
    logging.info(f"Split text into {len(chunks)} chunks for TTS.")
    return chunks

# ======== PROVIDER-SPECIFIC GENERATION LOGIC ========

def _generate_with_google(text: str, voice_name: str, tts_client_instance) -> bytes:
    """
    Handles the TTS generation specifically for the Google Cloud provider.
    Returns the combined audio content as bytes.
    """
    logging.info(f"Generating audio with Google TTS, voice: {voice_name}")
    chunks = split_text_by_bytes(text)
    if not chunks:
        raise ValueError("Input text is empty or could not be processed into chunks for Google TTS.")

    try:
        lang_code = "-".join(voice_name.split("-")[:2])
    except Exception:
        logging.warning(f"Could not parse lang code from '{voice_name}'. Defaulting 'en-US'.")
        lang_code = "en-US"

    combined_audio = AudioSegment.empty()
    with tempfile.TemporaryDirectory(prefix="tts_google_chunks_") as chunk_processing_temp_dir:
        successful_chunk_files = []
        for i, chunk_text in enumerate(chunks):
            if not chunk_text.strip(): continue
            chunk_path = os.path.join(chunk_processing_temp_dir, f"chunk_{i}.mp3")
            synthesis_input = texttospeech.SynthesisInput(text=chunk_text)
            voice_params = texttospeech.VoiceSelectionParams(language_code=lang_code, name=voice_name)
            audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
            response = tts_client_instance.synthesize_speech(
                request={"input": synthesis_input, "voice": voice_params, "audio_config": audio_config}
            )
            with open(chunk_path, "wb") as out:
                out.write(response.audio_content)
            successful_chunk_files.append(chunk_path)
        
        for file_path in successful_chunk_files:
            segment = AudioSegment.from_mp3(file_path)
            combined_audio += segment

    if len(combined_audio) == 0:
        raise ValueError("Google TTS process resulted in no valid audio output.")
    
    # Return the raw bytes of the combined audio
    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as temp_f:
        combined_audio.export(temp_f.name, format="mp3")
        return temp_f.read()

def _generate_with_elevenlabs(text: str, voice_name: str, elevenlabs_client_instance, stability: float, similarity_boost: float) -> bytes:
    """
    Handles the TTS generation specifically for the ElevenLabs provider.
    """
    logging.info(f"Generating audio with ElevenLabs TTS, voice: {voice_name}, stability: {stability}, similarity_boost: {similarity_boost}")
    settings = VoiceSettings(stability=stability, similarity_boost=similarity_boost)
    
    response = elevenlabs_client_instance.generate(
        text=text,
        voice=voice_name,
        model='eleven_multilingual_v2',
        voice_settings=settings
    )
    
    # FIX: Safety check for different ElevenLabs SDK versions.
    # Older versions return bytes directly. Newer V1 SDKs return a generator of bytes.
    if isinstance(response, bytes):
        return response
    else:
        return b"".join(response)

# ======== MAIN TTS & LOCAL SAVE FUNCTION (PROVIDER-AWARE) ========
def text_to_speech_and_save_locally(
    text: str,
    voice_name: str,
    provider: str,
    suggested_llm_basename: str | None,
    tts_client_instance: texttospeech.TextToSpeechClient, # Keep for Google
    elevenlabs_client_instance,
    stability: float = 0.75,
    similarity_boost: float = 0.75
) -> tuple[str | None, str | None, str | None, str, str]:
    """
    Converts text to speech using the specified provider, saves M4A and TXT locally.
    """
    # 1. Determine the final base filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    if suggested_llm_basename and suggested_llm_basename != "untitled":
        final_basename_used = clean_filename(suggested_llm_basename)
    else:
        final_basename_used = f"speech_{timestamp}"

    # 2. Create the specific output directory
    specific_output_dir_abs_path = os.path.join(GENERATED_OUTPUT_PARENT_DIR, final_basename_used)
    os.makedirs(specific_output_dir_abs_path, exist_ok=True)

    # 3. Provider-based dispatch to get audio content
    audio_content_bytes = None
    if provider == 'google':
        if not tts_client_instance:
            raise ConnectionError("Google TTS client instance not provided for 'google' provider.")
        audio_content_bytes = _generate_with_google(text, voice_name, tts_client_instance)
    elif provider == 'elevenlabs':
        if not elevenlabs_client_instance:
            raise ConnectionError("ElevenLabs client instance not provided for 'elevenlabs' provider.")
        audio_content_bytes = _generate_with_elevenlabs(text, voice_name, elevenlabs_client_instance, stability, similarity_boost)
    else:
        raise ValueError(f"Unsupported TTS provider: {provider}")

    if not audio_content_bytes:
        logging.warning(f"Provider '{provider}' returned no audio data. Skipping file save.")
        # Still return the directory path so the UI can report where it *would* have gone.
        return None, None, None, specific_output_dir_abs_path, final_basename_used

    # 4. Save the received audio bytes to files
    abs_mp3_path = None
    abs_m4a_path = None
    
    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as temp_f:
        temp_f.write(audio_content_bytes)
        temp_f.flush()
        audio_segment = AudioSegment.from_mp3(temp_f.name)

    mp3_filename_only = f"{final_basename_used}.mp3"
    abs_mp3_path = os.path.join(specific_output_dir_abs_path, mp3_filename_only)
    with open(abs_mp3_path, 'wb') as f:
        f.write(audio_content_bytes)

    if shutil.which("ffmpeg") is not None or shutil.which("avconv") is not None:
        m4a_filename_only = f"{final_basename_used}.m4a"
        abs_m4a_path_candidate = os.path.join(specific_output_dir_abs_path, m4a_filename_only)
        audio_segment.export(abs_m4a_path_candidate, format="mp4", codec="aac")
        abs_m4a_path = abs_m4a_path_candidate

    # 5. Create the TXT file
    txt_filename_only = f"{final_basename_used}.txt"
    abs_txt_path = os.path.join(specific_output_dir_abs_path, txt_filename_only)
    with open(abs_txt_path, 'w', encoding='utf-8') as f_txt:
        f_txt.write(text)

    return abs_mp3_path, abs_m4a_path, abs_txt_path, specific_output_dir_abs_path, final_basename_used

# ======== LLM FILENAME SUGGESTION FUNCTION (SYNCHRONOUS) ========
def suggest_filename_llm_sync(
    text_sample: str,
    llm_model_instance: genai.GenerativeModel | None
) -> tuple[str | None, str | None]:
    """
    Uses the provided LLM model instance synchronously to suggest a filename base.
    """
    if not llm_model_instance:
        return None, None
    raw_suggestion_text = None
    cleaned_suggestion_text = None
    try:
        llm_start_time = time.time()
        prompt_text = (text_sample[:600] + '...') if len(text_sample) > 600 else text_sample
        prompt = f"Suggest a very concise, descriptive filename base (3-5 words max, underscores_for_spaces, lowercase, alphanumeric_only, no_extension, no_quotes) for this text: '{prompt_text}'"

        safety_settings=[
            {"category": c, "threshold": "BLOCK_MEDIUM_AND_ABOVE"} for c in [
                "HARM_CATEGORY_HARASSMENT",
                "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "HARM_CATEGORY_DANGEROUS_CONTENT",
            ]
        ]
        generation_config = genai.types.GenerationConfig(
            candidate_count=1,
            max_output_tokens=30, # Short, for a filename
            temperature=0.4
        )

        response = llm_model_instance.generate_content(
            prompt,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        llm_duration = time.time() - llm_start_time

        if response.prompt_feedback and response.prompt_feedback.block_reason:
            logging.warning(f"LLM prompt blocked: {response.prompt_feedback.block_reason}")
            raw_suggestion_text = f"blocked_{response.prompt_feedback.block_reason.name}"
        elif not response.candidates:
            logging.warning(f"LLM returned no candidates. Feedback: {response.prompt_feedback}")
            raw_suggestion_text = "llm_no_candidates"
        else:
            candidate = response.candidates[0]
            finish_reason_name = candidate.finish_reason.name if hasattr(candidate.finish_reason, 'name') else "UNKNOWN_REASON"

            if finish_reason_name == "SAFETY":
                safety_ratings_str = ", ".join([
                    f"{r.category.name}: {r.probability.name}" for r in candidate.safety_ratings
                    if hasattr(r, 'category') and hasattr(r.category, 'name') and hasattr(r, 'probability') and hasattr(r.probability, 'name')
                ])
                logging.warning(f"LLM candidate blocked by safety: [{safety_ratings_str}]")
                raw_suggestion_text = f"blocked_safety_{finish_reason_name}"
            elif finish_reason_name not in ["STOP", "MAX_TOKENS", "UNSPECIFIED"]: # UNSPECIFIED can sometimes have content
                logging.warning(f"LLM stopped unexpectedly: {finish_reason_name}")
                raw_suggestion_text = f"stopped_{finish_reason_name}"

            if not raw_suggestion_text: # If not blocked or stopped unexpectedly
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts') and candidate.content.parts and hasattr(candidate.content.parts[0], 'text'):
                    try:
                        raw_suggestion_text = candidate.content.parts[0].text.strip().replace('"', '').replace("'", "")
                        if not raw_suggestion_text: # Empty string after stripping
                            logging.warning("LLM empty suggestion text.")
                            raw_suggestion_text = "llm_empty_suggestion"
                        else:
                            # We primarily return the raw suggestion for `clean_filename` to process
                            cleaned_suggestion_text = clean_filename(raw_suggestion_text) # For logging/debug
                            if not cleaned_suggestion_text or cleaned_suggestion_text == "untitled":
                                logging.info(f"LLM suggestion ('{raw_suggestion_text}') invalid after cleaning.")
                                # Keep raw_suggestion_text as is, let `clean_filename` in main function handle it
                    except Exception as text_access_e:
                        logging.warning(f"LLM text access failed: {text_access_e}")
                        raw_suggestion_text = "llm_text_access_error"
                else:
                    logging.warning("LLM candidate has no valid content parts or text.")
                    raw_suggestion_text = "llm_no_content_parts"

        logging.info(f"LLM suggestion raw: '{raw_suggestion_text}', cleaned for log: ('{cleaned_suggestion_text}') took {llm_duration:.2f}s.")
        return raw_suggestion_text, cleaned_suggestion_text if raw_suggestion_text and "error" not in raw_suggestion_text and "blocked" not in raw_suggestion_text and "empty" not in raw_suggestion_text else None

    except Exception as e:
        logging.exception("Error during LLM suggestion:")
        return f"llm_error_{type(e).__name__}", None