import speech_recognition as sr

def record_and_transcribe(output_file="transcription.txt"):
    r = sr.Recognizer()
    # Use the default microphone as the audio source
    with sr.Microphone() as source:
        print("Adjusting for ambient noise, please wait...")
        r.adjust_for_ambient_noise(source)
        print("Listening... Please speak now.")
        audio = r.listen(source)
    
    try:
        print("Recognizing speech...")
        transcription = r.recognize_google(audio)
        print("Transcription:", transcription)
        # Write the transcription to a text file
        with open(output_file, "w") as f:
            f.write(transcription)
        print(f"Transcription saved to {output_file}")
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand audio.")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition service; {0}".format(e))

if __name__ == "__main__":
    record_and_transcribe()
