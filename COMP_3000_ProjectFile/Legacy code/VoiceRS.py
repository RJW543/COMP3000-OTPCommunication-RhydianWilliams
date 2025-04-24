@ -1,50 +0,0 @@
import speech_recognition as sr

recognized_text = ""

def callback(recognizer, audio):
    """This callback function is called each time audio is captured."""
    global recognized_text
    try:
        # Convert the audio to text using Google's speech recognition service.
        transcription = recognizer.recognize_google(audio)
        recognized_text += transcription + "\n"
        print("Recognized:", transcription)
    except sr.UnknownValueError:
        print("Could not understand audio.")
    except sr.RequestError as e:
        print("Request error from Google Speech Recognition service; {0}".format(e))

def record_and_transcribe(output_file="transcription.txt"):
    r = sr.Recognizer()
    # Use the default microphone as the audio source.
    mic = sr.Microphone()
    
    # Adjustment code for the ambient noise.
    with mic as source:
        print("Adjusting for ambient noise, please wait...")
        r.adjust_for_ambient_noise(source)
        print("Ready to record. Speak now.")
    
    # Start background listening. The returned function can be called to stop listening.
    stop_listening = r.listen_in_background(mic, callback)
    print("Recording started... Press Enter to stop recording.")
    
    # Wait for the user to press Enter in the command line to stop recording.
    input()
    
    # Stop background listening.
    stop_listening(wait_for_stop=False)
    print("Recording stopped.")
    
    # Write the transcription to a text file.
    with open(output_file, "w") as f:
        f.write(recognized_text)
    print(f"Transcription saved to {output_file}")

if __name__ == "__main__":
    answer = input("Do you want to start recording? (y/n): ").strip().lower()
    if answer == "y":
        record_and_transcribe()
    else:
        print("Exiting without recording.")