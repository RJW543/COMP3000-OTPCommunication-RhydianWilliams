import tkinter as tk
import socket
import threading
import speech_recognition as sr
import pyttsx3

class CombinedClientApp:
    def __init__(self, master, server_ip="127.0.0.1", server_port=9999):
        self.master = master
        self.master.title("Combined Client - Two-Way Audio Chat")

        # Server details
        self.server_ip = server_ip
        self.server_port = server_port

        # State
        self.client_name = None
        self.running = True

        # TTS engine
        self.tts_engine = pyttsx3.init()

        # Create UI
        self.create_widgets()

        # Create a UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind locally (any free port)
        self.sock.bind(("", 0))

        # Thread for receiving messages
        self.listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        self.listener_thread.start()

    def create_widgets(self):
        # Name entry
        self.name_label = tk.Label(self.master, text="Enter your name (unique!):")
        self.name_label.pack(pady=2)

        self.name_entry = tk.Entry(self.master)
        self.name_entry.pack(pady=2)

        self.register_button = tk.Button(self.master, text="Register", command=self.register)
        self.register_button.pack(pady=5)

        self.record_button = tk.Button(self.master, text="Record & Send", command=self.record_and_send, state="disabled")
        self.record_button.pack(pady=10)

        self.status_label = tk.Label(self.master, text="Status: Not registered")
        self.status_label.pack(pady=5)

        self.last_received_label = tk.Label(self.master, text="Last Received: None")
        self.last_received_label.pack(pady=5)

    def register(self):
        """
        Register the client name with the server so the server knows how to forward messages to us.
        """
        name = self.name_entry.get().strip()
        if not name:
            self.status_label.config(text="Please enter a name before registering.")
            return
        self.client_name = name

        # Send a registration packet: "REGISTER: <name>"
        register_msg = f"REGISTER: {self.client_name}"
        self.sock.sendto(register_msg.encode("utf-8"), (self.server_ip, self.server_port))
        self.status_label.config(text=f"Registered as {self.client_name}.")
        self.record_button.config(state="normal")

    def record_and_send(self):
        """
        Capture audio, convert to text, and send to the server.
        """
        if not self.client_name:
            self.status_label.config(text="You must register first!")
            return

        self.status_label.config(text="Status: Recording...")
        self.master.update_idletasks()

        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=1)
            audio_data = r.listen(source)

        self.status_label.config(text="Status: Converting to text...")
        self.master.update_idletasks()

        try:
            recognized_text = r.recognize_google(audio_data)
            self.status_label.config(text=f"Sending: {recognized_text}")

            # Format: "Name: text"
            msg = f"{self.client_name}: {recognized_text}"
            self.sock.sendto(msg.encode("utf-8"), (self.server_ip, self.server_port))

            self.status_label.config(text="Status: Sent!")
        except sr.UnknownValueError:
            self.status_label.config(text="Could not understand audio.")
        except sr.RequestError as e:
            self.status_label.config(text=f"API error: {e}")

    def listen_for_messages(self):
        """
        Thread loop that receives incoming text messages from the server and plays them via TTS.
        """
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                text_received = data.decode("utf-8", errors="ignore").strip()
                # Expect format: "OtherName: message"
                if ":" not in text_received:
                    continue
                sender_name, message = text_received.split(":", 1)
                sender_name = sender_name.strip()
                message = message.strip()

                # Update GUI
                self.last_received_label.config(text=f"Last Received from {sender_name}: {message}")
                self.status_label.config(text="Status: Speaking...")

                # Speak
                self.tts_engine.say(message)
                self.tts_engine.runAndWait()

                self.status_label.config(text="Status: Idle")
            except Exception as e:
                print(f"Client error receiving data: {e}")
                break

    def on_closing(self):
        self.running = False
        self.sock.close()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = CombinedClientApp(root, server_ip="127.0.0.1", server_port=9999)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
