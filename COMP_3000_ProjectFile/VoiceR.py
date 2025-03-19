import tkinter as tk
from tkinter import ttk
import speech_recognition as sr
import pyttsx3

# Global variable to store the recognized text and the stop function
recognized_text = ""
stop_listening = None

# Initialize recognizer and text-to-speech engine
r = sr.Recognizer()
engine = pyttsx3.init()

def callback(recognizer, audio):
    global recognized_text
    try:
        # Use Google's API to convert speech into text
        text = recognizer.recognize_google(audio)
        # Append the recognized text to our global variable
        recognized_text += text + " "
    except Exception as e:
        print("Recognition error:", e)

def start_recording():
    global stop_listening, recognized_text, mic
    # Clear any previous text
    recognized_text = ""
    # Retrieve the selected input device index (assumes dropdown items formatted as "index - name")
    selected_input = input_device_var.get().split(" - ")[0]
    try:
        device_index = int(selected_input)
    except ValueError:
        device_index = None
    # Create a Microphone instance with the chosen device
    mic = sr.Microphone(device_index=device_index)
    # Adjust for ambient noise (optional, but can help recognition)
    with mic as source:
        r.adjust_for_ambient_noise(source)
    # Start background listening – this returns a function that stops the listener
    stop_listening = r.listen_in_background(mic, callback)
    start_button.config(state="disabled")
    stop_button.config(state="normal")
    print("Recording started...")

def stop_recording():
    global stop_listening
    if stop_listening:
        stop_listening(wait_for_stop=False)
    start_button.config(state="normal")
    stop_button.config(state="disabled")
    print("Recording stopped.")
    # If output mode is "Speak", use pyttsx3 to speak the final recognized text
    if output_mode_var.get() == "Speak":
        engine.say(recognized_text)
        engine.runAndWait()

def periodic_update():
    # If output mode is "GUI", update the text widget with recognized text
    if output_mode_var.get() == "GUI":
        output_text_widget.config(state="normal")
        output_text_widget.delete(1.0, tk.END)
        output_text_widget.insert(tk.END, recognized_text)
        output_text_widget.config(state="disabled")
    # For "Console" mode, we print the latest text (this will print periodically)
    elif output_mode_var.get() == "Console":
        print("Current recognized text:", recognized_text)
    # Schedule the next update after 1 second (1000 ms)
    root.after(1000, periodic_update)

root = tk.Tk()
root.title("Voice Recorder & Speech Recognizer")

# Create a frame for input and output selection
config_frame = ttk.Frame(root, padding="10")
config_frame.pack(fill=tk.X)

# Input Device Selection
input_device_var = tk.StringVar(root)
# Get available microphone names (each item is formatted with its index)
mic_names = sr.Microphone.list_microphone_names()
input_options = [f"{i} - {name}" for i, name in enumerate(mic_names)]
input_device_var.set(input_options[0])

ttk.Label(config_frame, text="Input Device:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
input_menu = ttk.OptionMenu(config_frame, input_device_var, input_options[0], *input_options)
input_menu.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

# Output Mode Selection
output_mode_var = tk.StringVar(root)
output_modes = ["GUI", "Console", "Speak"]
output_mode_var.set(output_modes[0])

ttk.Label(config_frame, text="Output Mode:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
output_menu = ttk.OptionMenu(config_frame, output_mode_var, output_modes[0], *output_modes)
output_menu.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

# Start and Stop Buttons
button_frame = ttk.Frame(root, padding="10")
button_frame.pack(fill=tk.X)

start_button = ttk.Button(button_frame, text="Start Recording", command=start_recording)
start_button.pack(side=tk.LEFT, padx=5)

stop_button = ttk.Button(button_frame, text="Stop Recording", command=stop_recording, state="disabled")
stop_button.pack(side=tk.LEFT, padx=5)

# Text widget to display recognized text when output mode is set to GUI
output_text_widget = tk.Text(root, height=10, width=50, state="disabled")
output_text_widget.pack(padx=10, pady=10)

# Begin periodic update for the GUI text widget or console output
root.after(1000, periodic_update)

root.mainloop()
