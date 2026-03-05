# Neural TTS Synthesizer

A Flask-based web application that converts text to speech using Google Cloud Text-to-Speech, streams the audio to the browser in real-time, and uses Google Gemini AI to intelligently generate filenames for the saved audio.

## Setup
1. Clone the repository.
2. Create a virtual environment: `python -m venv venv` and activate it.
3. Install dependencies: `pip install -r requirements.txt`
4. Create a `.env` file with your `GEMINI_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS`.
5. Run the app: `python app.py`