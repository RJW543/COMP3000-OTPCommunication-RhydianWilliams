import socket
import threading
import json
import pyaudio
import tkinter as tk
from tkinter import ttk, messagebox

# Constants
PAGE_SIZE = 5000  # OTP Page length
HEADER_SIZE = 8   # First 8 bytes are the sync header
CHUNK_FRAMES = 1024  # Number of frames per chunk
SAMPLE_WIDTH = 2  # 16-bit audio (2 bytes per frame)
CHUNK_SIZE = CHUNK_FRAMES * SAMPLE_WIDTH  # Total bytes per audio chunk

class OTPReader:
    """Reads OTP bytes from the pad while skipping headers."""
    def __init__(self, filename, page_size=PAGE_SIZE, header_size=HEADER_SIZE, initial_offset=0):
        self.page_size = page_size
        self.header_size = header_size
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        otp_string = ''.join(lines)
        if len(otp_string) % page_size != 0:
            print("Warning: OTP file length is not a multiple of page size!")
        self.data = otp_string.encode('ascii')
        self.current_index = initial_offset

    def read(self, n):
        """Returns n OTP bytes while skipping headers."""
        result = bytearray()
        while len(result) < n:
            page_start = (self.current_index // self.page_size) * self.page_size
            if self.current_index < page_start + self.header_size:
                self.current_index = page_start + self.header_size
            page_end = page_start + self.page_size
            bytes_left = page_end - self.current_index
            to_read = min(n - len(result), bytes_left)
            if self.current_index + to_read > len(self.data):
                raise Exception("Not enough OTP data! Pad exhausted.")
            result.extend(self.data[self.current_index:self.current_index + to_read])
            self.current_index += to_read
        return bytes(result)

class VoiceClientGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OTP Encrypted Voice Call")
        self.geometry("400x350")
        self.resizable(False, False)

        # Variables
        self.ngrok_host_var = tk.StringVar()
        self.ngrok_port_var = tk.StringVar()
        self.server_host = None
        self.server_port = None

        self.user_id_var = tk.StringVar()
        self.target_id_var = tk.StringVar()
        self.otp_file = "otp_cipher.txt"

        self.running = False
        self.sock = None
        self.send_thread = None
        self.recv_thread = None

        self.create_widgets()

    def create_widgets(self):
        """Create and layout the widgets in the GUI."""
        frame = ttk.Frame(self)
        frame.pack(padx=10, pady=10, fill="x", expand=True)

        # Ngrok Host & Port
        ttk.Label(frame, text="Ngrok Host:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.ngrok_host_var).grid(row=0, column=1, sticky="ew")

        ttk.Label(frame, text="Ngrok Port:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.ngrok_port_var).grid(row=1, column=1, sticky="ew")

        ttk.Button(frame, text="Set Server Address", command=self.set_server_address).grid(row=2, column=0, columnspan=2, pady=5)

        # User ID Input
        ttk.Label(frame, text="Your User ID:").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.user_id_var).grid(row=3, column=1, sticky="ew")

        ttk.Button(frame, text="Connect to Server", command=self.connect_to_server).grid(row=4, column=0, columnspan=2, pady=5)

        # Recipient ID Input
        ttk.Label(frame, text="Recipient ID:").grid(row=5, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.target_id_var).grid(row=5, column=1, sticky="ew")

        # Call & Hangup Buttons
        self.call_button = ttk.Button(frame, text="Call", command=self.start_call, state="disabled")
        self.call_button.grid(row=6, column=0, pady=5)

        self.hangup_button = ttk.Button(frame, text="Hang Up", command=self.end_call, state="disabled")
        self.hangup_button.grid(row=6, column=1, pady=5)

        self.status_label = ttk.Label(self, text="Status: Not Connected", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=10)

        frame.columnconfigure(1, weight=1)

    def set_server_address(self):
        """Set the Ngrok tunnel address based on user input."""
        self.server_host = self.ngrok_host_var.get().strip()
        self.server_port = self.ngrok_port_var.get().strip()

        if not self.server_host or not self.server_port:
            messagebox.showerror("Error", "Please enter a valid Ngrok Host and Port.")
            return

        self.status_label.config(text=f"Server set to {self.server_host}:{self.server_port}")

    def connect_to_server(self):
        """Attempt to connect to the server."""
        if not self.server_host or not self.server_port:
            messagebox.showerror("Error", "You must set the server address first.")
            return

        self.call_button.config(state="normal")
        self.status_label.config(text="Connected. Ready to Call.")

    def start_call(self):
        """Start a voice call by connecting to the server."""
        user_id = self.user_id_var.get().strip()
        target_id = self.target_id_var.get().strip()

        if not user_id or not target_id:
            messagebox.showerror("Input Error", "Please enter your User ID and Recipient ID.")
            return

        try:
            server_port = int(self.server_port)
        except ValueError:
            messagebox.showerror("Input Error", "Server Port must be an integer.")
            return

        self.send_otp = OTPReader(self.otp_file, initial_offset=0)
        self.recv_otp = OTPReader(self.otp_file, initial_offset=PAGE_SIZE)

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_host, server_port))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            return

        login_message = json.dumps({"user_id": user_id, "target_id": target_id}) + "\n"
        self.sock.sendall(login_message.encode('utf-8'))

        self.running = True
        self.call_button.config(state="disabled")
        self.hangup_button.config(state="normal")
        self.status_label.config(text="Call in progress...")

        self.send_thread = threading.Thread(target=self.send_audio, daemon=True)
        self.recv_thread = threading.Thread(target=self.receive_audio, daemon=True)
        self.send_thread.start()
        self.recv_thread.start()

    def end_call(self):
        """Hang up the call and close the connection."""
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

        self.call_button.config(state="normal")
        self.hangup_button.config(state="disabled")
        self.status_label.config(text="Call ended.")

    def send_audio(self):
        """Record and send encrypted voice data."""
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=CHUNK_FRAMES)
        while self.running:
            audio_data = stream.read(CHUNK_FRAMES)
            otp_bytes = self.send_otp.read(len(audio_data))
            encrypted_chunk = bytes(a ^ b for a, b in zip(audio_data, otp_bytes))
            self.sock.sendall(encrypted_chunk)
        stream.close()
        p.terminate()

    def receive_audio(self):
        """Receive and decrypt incoming voice data."""
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, output=True, frames_per_buffer=CHUNK_FRAMES)
        while self.running:
            data = self.sock.recv(CHUNK_SIZE)
            otp_bytes = self.recv_otp.read(len(data))
            decrypted_chunk = bytes(a ^ b for a, b in zip(data, otp_bytes))
            stream.write(decrypted_chunk)
        stream.close()
        p.terminate()

if __name__ == "__main__":
    app = VoiceClientGUI()
    app.mainloop()
