import subprocess
import time
import os

# --- CONFIGURATION ---
# 1. The list of websites you want to open
urls = [
    "https://aistudio.google.com/prompts/new_chat",
    "https://deepbreathe.app",
    "https://www.youtube.com/watch?v=1T2l65G0q04", # The 40Hz video
    "http://127.0.0.1:5001" # Your local app
]

# 2. Path to your python app (We use current directory assuming this script is next to app.py)
# If this script is elsewhere, change os.getcwd() to "/Users/william/path/to/your/folder"
project_path = os.getcwd() 

def start_server():
    print("Starting SynthApp Server...")
    # This runs your app.py in the background
    subprocess.Popen(["python3", "app.py"], cwd=project_path)
    time.sleep(3) # Wait a few seconds for the server to spin up

def open_and_fullscreen(url):
    print(f"Opening {url}...")
    
    # 1. Open Chrome in a NEW window (-na "Google Chrome" --args --new-window)
    subprocess.run(["open", "-na", "Google Chrome", "--args", "--new-window", url])
    
    # 2. Wait for the window to appear (Critical for the next step to work)
    time.sleep(2)
    
    # 3. Use AppleScript to hit "Cmd + Ctrl + F" to make it Full Screen (Create a Space)
    # This creates that "Swipeable" effect you like.
    apple_script = """
    tell application "System Events"
        tell process "Google Chrome"
            set frontmost to true
            keystroke "f" using {command down, control down}
        end tell
    end tell
    """
    subprocess.run(["osascript", "-e", apple_script])

def main():
    # Step 1: Start the local server
    start_server()

    # Step 2: Open each URL and maximize it into a new Space
    for url in urls:
        open_and_fullscreen(url)
        # Add a small buffer between windows so macOS doesn't get confused
        time.sleep(1)

if __name__ == "__main__":
    main()