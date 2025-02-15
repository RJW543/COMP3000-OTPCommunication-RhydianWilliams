import socket
import threading
import tkinter as tk
from tkinter import messagebox
import pyaudio
import time

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 50007

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

class VoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Simple Voice Call Demo")
        
        # UI Elements
        tk.Label(master, text="Your User ID:").grid(row=0, column=0, padx=5, pady=5)
        self.user_id_entry = tk.Entry(master)
        self.user_id_entry.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(master, text="Call Target ID:").grid(row=1, column=0, padx=5, pady=5)
        self.target_id_entry = tk.Entry(master)
        self.target_id_entry.grid(row=1, column=1, padx=5, pady=5)

        self.call_button = tk.Button(master, text="Call", command=self.call_user)
        self.call_button.grid(row=2, column=0, padx=5, pady=5)

        self.accept_button = tk.Button(master, text="Accept Call", command=self.accept_call, state=tk.DISABLED)
        self.accept_button.grid(row=2, column=1, padx=5, pady=5)

        # Network and audio attributes
        self.socket = None
        self.user_id = None
        self.target_id = None
        self.is_calling = False
        self.stream = None
        self.audio_interface = pyaudio.PyAudio()
        
        # Start in a "disconnected" state
        self.connected = False
        self.incoming_call_from = None

    def connect_to_server(self):
        """
        Connect to the forwarding server and send user ID.
        """
        if self.socket is None:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((SERVER_HOST, SERVER_PORT))
            self.socket.setblocking(True)
            # Send user_id
            self.socket.sendall(self.user_id.encode('utf-8'))

            # Start a thread to listen for server messages
            listener_thread = threading.Thread(target=self.listen_server, daemon=True)
            listener_thread.start()

            self.connected = True

    def listen_server(self):
        """
        Listen for server messages such as INCOMING_CALL, CALL_ACCEPTED, or AUDIO data.
        """
        while True:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break

                if data.startswith(b"INCOMING_CALL|"):
                    # Format: INCOMING_CALL|<caller_id>
                    parts = data.decode('utf-8').split("|")
                    if len(parts) == 2:
                        caller_id = parts[1]
                        self.incoming_call_from = caller_id
                        print(f"[CLIENT] Incoming call from {caller_id}")
                        # Enable Accept button
                        self.accept_button.config(state=tk.NORMAL)
                        messagebox.showinfo("Incoming Call", f"Call from {caller_id}")

                elif data.startswith(b"CALL_ACCEPTED|"):
                    # Format: CALL_ACCEPTED|<target_id>
                    parts = data.decode('utf-8').split("|")
                    if len(parts) == 2:
                        target_id = parts[1]
                        print(f"[CLIENT] Call accepted by {target_id}")
                        self.is_calling = True
                        self.start_audio_stream()

                elif data.startswith(b"ERROR|"):
                    msg = data.decode('utf-8')
                    print("[CLIENT] " + msg)
                    messagebox.showerror("Error", msg)

                elif data.startswith(b"AUDIO|"):
                    # Extract raw audio after "AUDIO|"
                    header, raw_audio = data.split(b'|', 1)
                    if self.stream is not None:
                        self.stream.write(raw_audio)
                else:
                    # Possibly raw audio fallback
                    # Not used in this simple example
                    pass

            except Exception as e:
                print("[CLIENT] Exception while listening to server:", e)
                break

    def call_user(self):
        """
        Initiate a call to the target user.
        """
        if not self.connected:
            # Connect on-demand if not connected
            self.user_id = self.user_id_entry.get().strip()
            if not self.user_id:
                messagebox.showerror("Error", "Please enter your user ID first!")
                return
            self.connect_to_server()

        self.target_id = self.target_id_entry.get().strip()
        if self.target_id:
            message = f"CALL|{self.target_id}"
            self.socket.sendall(message.encode('utf-8'))
            print(f"[CLIENT] Initiated call to {self.target_id}")
        else:
            messagebox.showerror("Error", "Please enter a target user ID.")

    def accept_call(self):
        """
        Accept an incoming call from self.incoming_call_from.
        """
        if self.incoming_call_from:
            message = f"ACCEPT|{self.incoming_call_from}"
            self.socket.sendall(message.encode('utf-8'))
            # Disable Accept button
            self.accept_button.config(state=tk.DISABLED)
            self.is_calling = True
            self.start_audio_stream()
        else:
            messagebox.showerror("Error", "No incoming call to accept.")

    def start_audio_stream(self):
        """
        Start capturing audio from mic and sending to server.
        Also prepare for playback.
        """
        # Initialise PyAudio streaming
        if self.stream is None:
            self.stream = self.audio_interface.open(format=FORMAT,
                                                    channels=CHANNELS,
                                                    rate=RATE,
                                                    input=True,
                                                    output=True,
                                                    frames_per_buffer=CHUNK)
        # Start a thread to capture audio from microphone and send to server
        capture_thread = threading.Thread(target=self.capture_audio, daemon=True)
        capture_thread.start()

    def capture_audio(self):
        """
        Continuously capture mic audio and send to server as 'AUDIO|' packets.
        """
        while self.is_calling:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                self.socket.sendall(b"AUDIO|" + data)
            except Exception as e:
                print("[CLIENT] Audio capture error:", e)
                break
        print("[CLIENT] Stopped capturing audio.")

def main():
    root = tk.Tk()
    client_app = VoiceClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()
