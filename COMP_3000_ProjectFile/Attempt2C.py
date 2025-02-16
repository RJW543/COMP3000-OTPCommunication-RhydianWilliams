# otp_voice_client.py

import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import pyaudio
import fcntl
from pathlib import Path

# ---------------------------
#       OTP FUNCTIONS
# ---------------------------
def load_otp_pages(file_name="otp_cipher.txt"):
    """
    Loads lines from otp_cipher.txt, each line has:
    8-char identifier + random data
    Example: ABC12345<lots_of_random_bytes>
    """
    otp_pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        return otp_pages
    with file_path.open("r") as file:
        for line in file:
            line = line.strip()
            if len(line) < 8:
                continue
            identifier = line[:8]
            content = line[8:]
            otp_pages.append((identifier, content))
    return otp_pages

def load_used_pages(file_name="used_pages.txt"):
    """
    Returns a set of used OTP identifiers so we never reuse a page.
    """
    file_path = Path(file_name)
    if not file_path.exists():
        return set()
    with file_path.open("r") as file:
        return {line.strip() for line in file}

def save_used_page(identifier, file_name="used_pages.txt"):
    """
    Appends the used page identifier to used_pages.txt
    """
    with open(file_name, "a") as file:
        file.write(f"{identifier}\n")

def get_next_otp_page_linux(otp_pages, used_identifiers, lock_file="used_pages.lock"):
    """
    Finds the next unused OTP page with a file lock so multiple processes
    don’t pick the same line at the same time (on Linux).
    """
    with open(lock_file, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        for identifier, content in otp_pages:
            if identifier not in used_identifiers:
                save_used_page(identifier)
                used_identifiers.add(identifier)
                fcntl.flock(lock, fcntl.LOCK_UN)
                return identifier, content

        fcntl.flock(lock, fcntl.LOCK_UN)
    return None, None

def encrypt_chunk(data_bytes, otp_content):
    """
    XOR each byte of audio data with the corresponding character from the OTP content.
    If OTP is shorter, the remainder is unencrypted (not secure in real usage).
    """
    length = min(len(data_bytes), len(otp_content))
    encrypted = bytearray(len(data_bytes))
    for i in range(length):
        encrypted[i] = data_bytes[i] ^ ord(otp_content[i])
    # Remainder is unchanged if OTP shorter
    for i in range(length, len(data_bytes)):
        encrypted[i] = data_bytes[i]
    return bytes(encrypted)

def decrypt_chunk(encrypted_bytes, otp_content):
    """
    XOR is symmetric, so we do the same operation to decrypt.
    """
    length = min(len(encrypted_bytes), len(otp_content))
    decrypted = bytearray(len(encrypted_bytes))
    for i in range(length):
        decrypted[i] = encrypted_bytes[i] ^ ord(otp_content[i])
    for i in range(length, len(encrypted_bytes)):
        decrypted[i] = encrypted_bytes[i]
    return bytes(decrypted)

# ---------------------------
#   GUI Voice Client
# ---------------------------
class OTPVoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Voice Client (ngrok Edition)")

        # -----------------------
        #  OTP Data & Bookkeeping
        # -----------------------
        self.otp_pages = load_otp_pages("otp_cipher.txt")
        self.used_identifiers = load_used_pages("used_pages.txt")

        # -----------------------
        #    GUI Widgets
        # -----------------------
        self.server_frame = tk.Frame(master)
        self.server_frame.pack(padx=10, pady=5)

        tk.Label(self.server_frame, text="Ngrok Host:").grid(row=0, column=0, padx=5, pady=3, sticky="e")
        self.ngrok_host_entry = tk.Entry(self.server_frame, width=20)
        self.ngrok_host_entry.grid(row=0, column=1, padx=5, pady=3)
        self.ngrok_host_entry.insert(0, "0.tcp.ngrok.io")  # typical for ngrok

        tk.Label(self.server_frame, text="Ngrok Port:").grid(row=1, column=0, padx=5, pady=3, sticky="e")
        self.ngrok_port_entry = tk.Entry(self.server_frame, width=20)
        self.ngrok_port_entry.grid(row=1, column=1, padx=5, pady=3)
        self.ngrok_port_entry.insert(0, "12345")  # example

        tk.Label(self.server_frame, text="Your userID:").grid(row=2, column=0, padx=5, pady=3, sticky="e")
        self.user_id_entry = tk.Entry(self.server_frame, width=20)
        self.user_id_entry.grid(row=2, column=1, padx=5, pady=3)
        self.user_id_entry.insert(0, "alice")

        tk.Button(self.server_frame, text="Connect", command=self.connect_to_server).grid(row=3, column=0, columnspan=2, pady=5)

        # Frame for call controls
        self.call_frame = tk.Frame(master)
        self.call_frame.pack(padx=10, pady=5)

        tk.Label(self.call_frame, text="Recipient userID:").grid(row=0, column=0, sticky="e", padx=5)
        self.recipient_id_entry = tk.Entry(self.call_frame, width=20)
        self.recipient_id_entry.grid(row=0, column=1, padx=5)
        self.recipient_id_entry.insert(0, "bob")

        self.start_call_button = tk.Button(self.call_frame, text="Start Call", command=self.start_call, state=tk.DISABLED)
        self.start_call_button.grid(row=1, column=0, padx=5, pady=3)

        self.stop_call_button = tk.Button(self.call_frame, text="Stop Call", command=self.stop_call, state=tk.DISABLED)
        self.stop_call_button.grid(row=1, column=1, padx=5, pady=3)

        # Log area
        self.log_area = scrolledtext.ScrolledText(master, height=10, width=50)
        self.log_area.pack(padx=10, pady=10)
        self.log_area.config(state=tk.DISABLED)

        # -----------------------
        #   Networking & Audio
        # -----------------------
        self.client_socket = None
        self.user_id = None
        self.recipient_id = None

        self.p = pyaudio.PyAudio()
        self.stream_in = None
        self.stream_out = None
        self.audio_running = False

        # Audio config
        self.RATE = 44100
        self.CHUNK = 1024

    def connect_to_server(self):
        """
        Connect to the server using the provided ngrok host/port, send userID, wait for response.
        """
        host = self.ngrok_host_entry.get().strip()
        port_str = self.ngrok_port_entry.get().strip()
        if not port_str.isdigit():
            self.log("Port must be a number.")
            return

        port = int(port_str)
        self.user_id = self.user_id_entry.get().strip()
        if not self.user_id:
            self.log("Please enter a valid userID.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            # Send our userID
            self.client_socket.sendall(self.user_id.encode("utf-8"))

            response = self.client_socket.recv(1024).decode("utf-8")
            if "already taken" in response or "Invalid" in response:
                self.log(f"Server response: {response}")
                self.client_socket.close()
                self.client_socket = None
                return

            self.log(f"Connected to {host}:{port} as '{self.user_id}'. Server says: {response}")
            self.start_call_button.config(state=tk.NORMAL)

            # Start thread to receive chunks
            threading.Thread(target=self.receive_chunks, daemon=True).start()

        except Exception as e:
            self.log(f"Connection error: {e}")

    def start_call(self):
        """
        Open input/output audio streams and start sending chunks to the specified recipient.
        """
        self.recipient_id = self.recipient_id_entry.get().strip()
        if not self.recipient_id:
            self.log("Please enter a recipient userID.")
            return

        # Open mic
        try:
            self.stream_in = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
        except Exception as e:
            self.log(f"Failed to open microphone: {e}")
            return

        # Open speaker
        try:
            self.stream_out = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
        except Exception as e:
            self.log(f"Failed to open speaker: {e}")
            if self.stream_in:
                self.stream_in.close()
            return

        self.audio_running = True
        self.start_call_button.config(state=tk.DISABLED)
        self.stop_call_button.config(state=tk.NORMAL)
        self.log(f"Call started with recipient: {self.recipient_id}")

        # Start sending audio in background
        threading.Thread(target=self.send_chunks, daemon=True).start()

    def stop_call(self):
        """
        Stop the audio threads and close streams.
        """
        self.audio_running = False
        self.stop_call_button.config(state=tk.DISABLED)
        self.start_call_button.config(state=tk.NORMAL)
        self.log("Call stopped.")

        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()
            self.stream_out = None

    def send_chunks(self):
        """
        Continuously read mic audio, OTP-encrypt each chunk, and send to the server.
        """
        while self.audio_running and self.client_socket:
            try:
                audio_data = self.stream_in.read(self.CHUNK, exception_on_overflow=False)
                # Grab next unused OTP page
                otp_identifier, otp_content = get_next_otp_page_linux(self.otp_pages, self.used_identifiers)
                if not otp_identifier or not otp_content:
                    self.log("No more OTP pages available. Stopping call.")
                    self.stop_call()
                    break

                encrypted_chunk = encrypt_chunk(audio_data, otp_content)
                # Convert to hex so we can safely transmit over TCP as text
                enc_hex = encrypted_chunk.hex()

                # Format: "recipientID|otpID:encHex"
                message = f"{self.recipient_id}|{otp_identifier}:{enc_hex}"
                self.client_socket.sendall(message.encode("utf-8"))

            except Exception as e:
                self.log(f"send_chunks error: {e}")
                break

        self.log("Stopped sending chunks.")

    def receive_chunks(self):
        """
        Continuously receive encrypted audio from server, decrypt, and play it.
        Expected format: "senderID|otpID:encHex"
        """
        while True:
            try:
                if not self.client_socket:
                    break

                data = self.client_socket.recv(8192).decode("utf-8")
                if not data:
                    self.log("Server closed connection.")
                    break

                # Could be an error message from server or a chunk
                if "|" not in data or ":" not in data:
                    self.log(f"Server message: {data}")
                    continue

                sender_id, payload = data.split("|", 1)
                otp_identifier, enc_hex = payload.split(":", 1)

                # Find matching OTP content
                otp_content = None
                for ident, content in self.otp_pages:
                    if ident == otp_identifier:
                        otp_content = content
                        break

                if not otp_content:
                    self.log(f"Unknown OTP identifier {otp_identifier}. Cannot decrypt.")
                    continue

                # Mark as used
                save_used_page(otp_identifier)
                self.used_identifiers.add(otp_identifier)

                encrypted_bytes = bytes.fromhex(enc_hex)
                decrypted_bytes = decrypt_chunk(encrypted_bytes, otp_content)

                if self.stream_out:
                    self.stream_out.write(decrypted_bytes)
                else:
                    self.log(f"Audio received from {sender_id}, but no output stream open.")

            except Exception as e:
                self.log(f"receive_chunks error: {e}")
                break

        self.log("Receive thread ended.")
        if self.client_socket:
            self.client_socket.close()
        self.log("Disconnected from server.")
        self.master.quit()

    def log(self, msg):
        """Append text to the log area."""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.yview(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = OTPVoiceClient(root)
    root.mainloop()
