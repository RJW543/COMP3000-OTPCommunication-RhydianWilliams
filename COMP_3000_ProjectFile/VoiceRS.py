import speech_recognition as sr

# Global variable to store the recognized text
recognized_text = ""

def callback(recognizer, audio):
    """This callback function is called each time audio is captured."""
    global recognized_text
    try:
        # Convert the audio to text using Google's speech recognition
        transcription = recognizer.recognize_google(audio)
        recognized_text += transcription + "\n"
        print("Recognized:", transcription)
    except sr.UnknownValueError:
        print("Could not understand audio.")
    except sr.RequestError as e:
        print("Request error from Google Speech Recognition service; {0}".format(e))

def record_and_transcribe(output_file="transcription.txt"):
    r = sr.Recognizer()
    # Use the default microphone as the audio source
    mic = sr.Microphone()
    
    # Adjust for ambient noise
    with mic as source:
        print("Adjusting for ambient noise, please wait...")
        r.adjust_for_ambient_noise(source)
        print("Ready to record. Speak now.")
    
    # Start background listening. The returned function can be called to stop listening.
    stop_listening = r.listen_in_background(mic, callback)
    print("Recording started... Press Enter to stop recording.")
    
    # Wait for user input in the command line to stop recording
    input()
    
    # Stop background listening
    stop_listening(wait_for_stop=False)
    print("Recording stopped.")
    
    # Write the transcription to a text file
    with open(output_file, "w") as f:
        f.write(recognized_text)
    print(f"Transcription saved to {output_file}")

if __name__ == "__main__":
    record_and_transcribe()
