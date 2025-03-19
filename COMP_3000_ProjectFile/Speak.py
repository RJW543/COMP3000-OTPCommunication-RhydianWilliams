import pyttsx3

def speak_transcription(file_path="transcription.txt"):
    # Initialize the text-to-speech engine.
    engine = pyttsx3.init()
    
    try:
        with open(file_path, "r") as f:
            text = f.read().strip()
        
        if not text:
            print("The transcription file is empty.")
            return
        
        print("Speaking the content of transcription.txt...")
        engine.say(text)
        engine.runAndWait()
        
    except FileNotFoundError:
        print(f"File '{file_path}' not found.")

if __name__ == "__main__":
    speak_transcription()
