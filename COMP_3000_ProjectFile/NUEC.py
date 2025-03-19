import tkinter as tk
import socket
import threading
import speech_recognition as sr
import pyttsx3

class CombinedClientApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Combined Client - Two-Way Audio Chat")

        # Variables
        self.server_host = None
        self.server_port = None
        self.client_name = None
        self.running = True

        # TTS engine
        self.tts_engine = pyttsx3.init()

        # Create UI
        self.create_widgets()

        # UDP Socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0))  # bind to any free local port

        # Start listening thread
        self.listener_thread = threading.Thread(target=self.listen_for_messages, daemon=True)
        self.listener_thread.start()

    def create_widgets(self):
        # Server info
        self.server_host_label = tk.Label(self.master, text="Server Host (LocalXpose domain/IP):")
        self.server_host_label.pack(pady=2)
        self.server_host_entry = tk.Entry(self.master)
        self.server_host_entry.insert(0, "127.0.0.1")  # example
        self.server_host_entry.pack(pady=2)

        self.server_port_label = tk.Label(self.master, text="Server Port:")
        self.server_port_label.pack(pady=2)
        self.server_port_entry = tk.Entry(self.master)
        self.server_port_entry.insert(0, "9999")  # example
        self.server_port_entry.pack(pady=2)

        # Name
        self.name_label = tk.Label(self.master, text="Your Name (unique):")
        self.name_label.pack(pady=2)
        self.name_entry = tk.Entry(self.master)
        self.name_entry.pack(pady=2)

        # Registration
        self.register_button = tk.Button(self.master, text="Register", command=self.register)
        self.register_button.pack(pady=5)

        # Record & Send
        self.record_button = tk.Button(self.master, text="Record & Send", command=self.record_and_send, state="disabled")
        self.record_button.pack(pady=10)

        # Status / Info
        self.status_label = tk.Label(self.master, text="Status: Not Registered")
        self.status_label.pack(pady=5)

        self.last_received_label = tk.Label(self.master, text="Last Received: None")
        self.last_received_label.pack(pady=5)

    def register(self):
        self.server_host = self.server_host_entry.get().strip()
        self.server_port = self.server_port_entry.get().strip()
        self.client_name = self.name_entry.get().strip()

        if not self.server_host or not self.server_port.isdigit() or not self.client_name:
            self.status_label.config(text="Please fill in all fields correctly.")
            return

        self.server_port = int(self.server_port)

        # Send registration
        reg_msg = f"REGISTER: {self.client_name}"
        try:
            self.sock.sendto(reg_msg.encode("utf-8"), (self.server_host, self.server_port))
            self.status_label.config(text=f"Registered as {self.client_name}.")
            self.record_button.config(state="normal")
        except Exception as e:
            self.status_label.config(text=f"Registration failed: {e}")

    def record_and_send(self):
        if not self.client_name:
            self.status_label.config(text="Not registered.")
            return

        self.status_label.config(text="Recording...")
        self.master.update_idletasks()

        r = sr.Recognizer()
        with sr.Microphone() as source:
            r.adjust_for_ambient_noise(source, duration=1)
            audio_data = r.listen(source)

        self.status_label.config(text="Converting to text...")
        self.master.update_idletasks()

        try:
            recognized_text = r.recognize_google(audio_data)
            self.status_label.config(text=f"Sending: {recognized_text}")

            msg = f"{self.client_name}: {recognized_text}"
            self.sock.sendto(msg.encode("utf-8"), (self.server_host, self.server_port))

            self.status_label.config(text="Sent!")
        except sr.UnknownValueError:
            self.status_label.config(text="Could not understand audio.")
        except sr.RequestError as e:
            self.status_label.config(text=f"API error: {e}")

    def listen_for_messages(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                text_received = data.decode("utf-8", errors="ignore").strip()
                if ":" not in text_received:
                    continue
                sender_name, message = text_received.split(":", 1)
                sender_name = sender_name.strip()
                message = message.strip()

                self.last_received_label.config(text=f"Last Received from {sender_name}: {message}")
                self.status_label.config(text="Speaking...")

                self.tts_engine.say(message)
                self.tts_engine.runAndWait()

                self.status_label.config(text="Idle")
            except Exception as e:
                print(f"Error receiving data: {e}")
                break

    def on_closing(self):
        self.running = False
        self.sock.close()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = CombinedClientApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
