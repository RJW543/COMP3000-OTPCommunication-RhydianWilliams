import tkinter as tk
import speech_recognition as sr

# Global variables for storing the transcription and the listener stop function.
recognized_text = ""
stop_listening = None

# Initialize the recognizer.
r = sr.Recognizer()

def callback(recognizer, audio):
    """Callback function for background listening.
       This function is called each time a phrase is detected."""
    global recognized_text
    try:
        # Transcribe the audio using Google's speech recognition service.
        text = recognizer.recognize_google(audio)
        # Append the recognized text (each new phrase on a new line)
        recognized_text += text + "\n"
    except sr.UnknownValueError:
        print("Could not understand the audio.")
    except sr.RequestError as e:
        print("Could not request results from Google Speech Recognition; {0}".format(e))

def start_recording():
    global stop_listening, recognized_text
    recognized_text = ""  # Clear any previous transcription.
    start_button.config(state="disabled")
    stop_button.config(state="normal")
    
    # Use the default microphone.
    mic = sr.Microphone()
    # Adjust for ambient noise.
    with mic as source:
        r.adjust_for_ambient_noise(source)
    # Start background listening.
    stop_listening = r.listen_in_background(mic, callback)
    print("Recording started...")

def stop_recording():
    global stop_listening
    if stop_listening:
        # Stop the background listener.
        stop_listening(wait_for_stop=False)
    start_button.config(state="normal")
    stop_button.config(state="disabled")
    print("Recording stopped.")
    
    # Write the transcription to a text file.
    with open("transcription.txt", "w") as f:
        f.write(recognized_text)
    print("Transcription saved to transcription.txt")

# --------------------- Setup the GUI ---------------------
root = tk.Tk()
root.title("Voice Recorder & Transcriber")

start_button = tk.Button(root, text="Start Recording", command=start_recording)
start_button.pack(padx=10, pady=10)

stop_button = tk.Button(root, text="Stop Recording", command=stop_recording, state="disabled")
stop_button.pack(padx=10, pady=10)

root.mainloop()
