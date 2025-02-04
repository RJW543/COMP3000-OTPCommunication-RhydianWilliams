"""
client_gui.py

A GUI client for real-time OTP-encrypted voice calls using a one-time pad.
This client allows the user to enter their user ID, target ID, server address,
and OTP file path. Once connected, the client encrypts microphone audio and sends
it to the server while simultaneously receiving encrypted audio, decrypting it,
and playing it back in real time.
"""

import socket
import threading
import json
import pyaudio
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

PAGE_SIZE = 5000      # OTP page length (each page is one line of 5000 characters)
HEADER_SIZE = 8       # first 8 characters are the sync header
CHUNK_FRAMES = 1024   # number of audio frames per chunk
SAMPLE_WIDTH = 2      # 16-bit audio (2 bytes per frame)
CHUNK_SIZE = CHUNK_FRAMES * SAMPLE_WIDTH  # total bytes per audio chunk

class OTPReader:
    """
    Reads OTP bytes from a text OTP file (with pages of PAGE_SIZE characters
    and a HEADER_SIZE sync header per page). 
    """
    def __init__(self, filename, page_size=PAGE_SIZE, header_size=HEADER_SIZE, initial_offset=0):
        self.page_size = page_size
        self.header_size = header_size
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        otp_string = ''.join(lines)
        if len(otp_string) % page_size != 0:
            print("Warning: OTP file length is not an exact multiple of the page size!")
        self.data = otp_string.encode('ascii')
        self.current_index = initial_offset

    def read(self, n):
        result = bytearray()
        while len(result) < n:
            current_page_start = (self.current_index // self.page_size) * self.page_size
            if self.current_index < current_page_start + self.header_size:
                self.current_index = current_page_start + self.header_size
            current_page_end = current_page_start + self.page_size
            bytes_left_in_page = current_page_end - self.current_index
            to_read = min(n - len(result), bytes_left_in_page)
            if self.current_index + to_read > len(self.data):
                raise Exception("Not enough OTP data! The pad is exhausted.")
            result.extend(self.data[self.current_index:self.current_index+to_read])
            self.current_index += to_read
        return bytes(result)

class VoiceClientGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OTP Encrypted Voice Call Client")
        self.geometry("400x300")
        self.resizable(False, False)

        # GUI variables
        self.user_id_var = tk.StringVar()
        self.target_id_var = tk.StringVar()
        self.server_host_var = tk.StringVar()
        self.server_port_var = tk.StringVar()
        self.otp_file_var = tk.StringVar(value="otp_cipher.txt")

        self.running = False
        self.sock = None
        self.send_thread = None
        self.recv_thread = None

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.Frame(self)
        frame.pack(padx=10, pady=10, fill="x", expand=True)

        ttk.Label(frame, text="Your User ID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.user_id_var).grid(row=0, column=1, sticky="ew")

        ttk.Label(frame, text="Target User ID:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.target_id_var).grid(row=1, column=1, sticky="ew")

        ttk.Label(frame, text="Server Host:").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.server_host_var).grid(row=2, column=1, sticky="ew")

        ttk.Label(frame, text="Server Port:").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.server_port_var).grid(row=3, column=1, sticky="ew")

        ttk.Label(frame, text="OTP File Path:").grid(row=4, column=0, sticky="w")
        otp_entry = ttk.Entry(frame, textvariable=self.otp_file_var)
        otp_entry.grid(row=4, column=1, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.browse_otp_file).grid(row=4, column=2, padx=(5, 0))

        self.call_button = ttk.Button(frame, text="Call", command=self.start_call)
        self.call_button.grid(row=5, column=0, pady=(10, 0))
        self.hangup_button = ttk.Button(frame, text="Hang Up", command=self.end_call, state="disabled")
        self.hangup_button.grid(row=5, column=1, pady=(10, 0))
        ttk.Button(frame, text="Quit", command=self.quit).grid(row=5, column=2, pady=(10, 0))

        self.status_label = ttk.Label(self, text="Status: Idle", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=(10, 0))

        frame.columnconfigure(1, weight=1)

    def browse_otp_file(self):
        filename = filedialog.askopenfilename(title="Select OTP File", filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
        if filename:
            self.otp_file_var.set(filename)

    def log_status(self, message):
        self.status_label.config(text="Status: " + message)

    def start_call(self):
        # Get and validate input values
        user_id = self.user_id_var.get().strip()
        target_id = self.target_id_var.get().strip()
        server_host = self.server_host_var.get().strip()
        server_port_str = self.server_port_var.get().strip()
        otp_file = self.otp_file_var.get().strip()

        if not user_id or not target_id or not server_host or not server_port_str or not otp_file:
            messagebox.showerror("Input Error", "Please fill in all fields.")
            return

        try:
            server_port = int(server_port_str)
        except ValueError:
            messagebox.showerror("Input Error", "Server Port must be an integer.")
            return

        if not os.path.exists(otp_file):
            messagebox.showerror("File Error", f"OTP file '{otp_file}' does not exist.")
            return

        # Determine OTP offsets
        if user_id < target_id:
            outgoing_offset = 0
            incoming_offset = PAGE_SIZE
        else:
            outgoing_offset = PAGE_SIZE
            incoming_offset = 0

        try:
            self.send_otp = OTPReader(otp_file, initial_offset=outgoing_offset)
            self.recv_otp = OTPReader(otp_file, initial_offset=incoming_offset)
        except Exception as e:
            messagebox.showerror("OTP Error", f"Error loading OTP file: {e}")
            return

        # Connect to the server
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((server_host, server_port))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            return

        # Send login message (JSON terminated by newline)
        login_message = json.dumps({"user_id": user_id, "target_id": target_id}) + "\n"
        try:
            self.sock.sendall(login_message.encode('utf-8'))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to send login message: {e}")
            return

        self.running = True
        self.call_button.config(state="disabled")
        self.hangup_button.config(state="normal")
        self.log_status("Call started...")

        # Start threads for sending and receiving audio
        self.send_thread = threading.Thread(target=self.send_audio, daemon=True)
        self.recv_thread = threading.Thread(target=self.receive_audio, daemon=True)
        self.send_thread.start()
        self.recv_thread.start()

    def end_call(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.call_button.config(state="normal")
        self.hangup_button.config(state="disabled")
        self.log_status("Call ended.")

    def send_audio(self):
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            input=True,
                            frames_per_buffer=CHUNK_FRAMES)
        except Exception as e:
            self.log_status("Audio input error: " + str(e))
            self.running = False
            p.terminate()
            return

        while self.running:
            try:
                audio_data = stream.read(CHUNK_FRAMES, exception_on_overflow=False)
                otp_bytes = self.send_otp.read(len(audio_data))
                encrypted_chunk = bytes(a ^ b for a, b in zip(audio_data, otp_bytes))
                self.sock.sendall(encrypted_chunk)
            except Exception as e:
                self.log_status("Send audio error: " + str(e))
                break
        stream.stop_stream()
        stream.close()
        p.terminate()

    def receive_audio(self):
        p = pyaudio.PyAudio()
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            output=True,
                            frames_per_buffer=CHUNK_FRAMES)
        except Exception as e:
            self.log_status("Audio output error: " + str(e))
            self.running = False
            p.terminate()
            return

        while self.running:
            try:
                data = self.recv_all(CHUNK_SIZE)
                if data is None:
                    break
                otp_bytes = self.recv_otp.read(len(data))
                decrypted_chunk = bytes(a ^ b for a, b in zip(data, otp_bytes))
                stream.write(decrypted_chunk)
            except Exception as e:
                self.log_status("Receive audio error: " + str(e))
                break
        stream.stop_stream()
        stream.close()
        p.terminate()

    def recv_all(self, n):
        data = b''
        while len(data) < n and self.running:
            try:
                packet = self.sock.recv(n - len(data))
            except Exception:
                return None
            if not packet:
                return None
            data += packet
        return data

    def on_closing(self):
        if self.running:
            if messagebox.askokcancel("Quit", "Call is in progress. Do you want to hang up and quit?"):
                self.end_call()
                self.destroy()
        else:
            self.destroy()

if __name__ == "__main__":
    app = VoiceClientGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
