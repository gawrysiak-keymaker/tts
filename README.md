# Google Cloud Text-to-Speech Web App

This project is a Python-based web application that provides a user-friendly interface for Google's powerful Cloud Text-to-Speech (TTS) API. It allows users to convert text into high-quality, natural-sounding speech, which can be played back in the browser and saved locally.

The application is built with Flask and leverages Google Cloud services for its core functionality. It also integrates a Generative AI model to intelligently suggest filenames based on the input text.

## Features

- **High-Quality Text-to-Speech:** Utilizes Google's WaveNet voices for realistic and natural speech synthesis.
- **Web-Based Interface:** Simple and intuitive UI for entering text, selecting a voice, and generating audio.
- **Intelligent Filename Suggestions:** Employs a Google Generative AI model (Gemini 1.5 Flash) to suggest concise and descriptive filenames for the generated audio.
- **Multiple Audio Formats:** Saves the generated speech in both MP3 and M4A formats.
- **Text File Generation:** Creates a corresponding text file alongside the audio files for easy reference.
- **Organized Output:** Automatically organizes the generated files into neatly named subdirectories within the `generated_output` folder.
- **Robust Error Handling:** Implements comprehensive error handling for API interactions and file operations.
- **Byte-Safe Text Chunking:** Safely splits large texts into smaller chunks to meet API limits without corrupting multi-byte characters.
- **Automatic Cleanup:** Includes a background thread to automatically clean up temporary files used for web playback.

## Setup and Installation

Follow these steps to set up and run the project on your local machine.

### 1. Prerequisites

- Python 3.7+
- `pip` for package installation
- `ffmpeg` (optional, but required for M4A file generation). You can install it using Homebrew on macOS (`brew install ffmpeg`) or a package manager on Linux.

### 2. Clone the Repository

```bash
git clone <repository_url>
cd <repository_directory>
```

### 3. Set Up a Virtual Environment

It is highly recommended to use a virtual environment to manage project dependencies.

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies

Install the required Python packages using the `requirements.txt` file.

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

The application requires API keys for Google Cloud TTS and the Google Generative AI model.

1.  **Create a `.env` file** in the root of the project directory.
2.  **Add the following variables** to the `.env` file:

    ```
    GOOGLE_APPLICATION_CREDENTIALS="path/to/your/google-cloud-service-account-key.json"
    GOOGLE_API_KEY="your_google_generative_ai_api_key"
    ```

    - `GOOGLE_APPLICATION_CREDENTIALS`: The absolute path to your Google Cloud service account JSON key file. This key must have permissions for the Text-to-Speech API.
    - `GOOGLE_API_KEY`: Your API key for the Google Generative AI service (e.g., Gemini).

## How to Run

Once you have completed the setup and installation steps, you can run the application with a single command.

```bash
python3 app.py
```

The application will start a local development server, and you can access it by opening your web browser and navigating to:

[http://127.0.0.1:5001](http://127.0.0.1:5001)

You can now use the web interface to convert text to speech. The generated files will be saved in the `generated_output` directory within the project folder.
# tts
# tts
# tts
