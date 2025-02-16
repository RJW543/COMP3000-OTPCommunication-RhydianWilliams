import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import pyaudio
import fcntl
from pathlib import Path

def load_otp_pages(file_name="otp_cipher.txt"):
    otp_pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        return otp_pages
    with file_path.open("r") as file:
        for line in file:
            line = line.strip()
            if len(line) < 8:
                continue  # skip invalid lines
            identifier = line[:8]
            content = line[8:]
            otp_pages.append((identifier, content))
    return otp_pages

def load_used_pages(file_name="used_pages.txt"):
    file_path = Path(file_name)
    if not file_path.exists():
        return set()
    with file_path.open("r") as file:
        return {line.strip() for line in file}

def save_used_page(identifier, file_name="used_pages.txt"):
    with open(file_name, "a") as file:
        file.write(f"{identifier}\n")

def get_next_otp_page_linux(otp_pages, used_identifiers, lock_file="used_pages.lock"):
    with open(lock_file, "w") as lock:
        # Acquire an exclusive lock
        fcntl.flock(lock, fcntl.LOCK_EX)

        for identifier, content in otp_pages:
            if identifier not in used_identifiers:
                # Mark it as used immediately
                save_used_page(identifier)
                used_identifiers.add(identifier)
                fcntl.flock(lock, fcntl.LOCK_UN)
                return identifier, content

        # Release the lock if no match found
        fcntl.flock(lock, fcntl.LOCK_UN)
    return None, None

def encrypt_chunk(data_bytes, otp_content):
    """
    data_bytes: raw bytes from microphone
    otp_content: string containing random OTP characters
    We need to XOR each byte with the ord of each OTP char.
    """
    if len(otp_content) < len(data_bytes):
        # If the OTP page is too short, we'll only encrypt partial
        length = len(otp_content)
    else:
        length = len(data_bytes)

    encrypted = bytearray(len(data_bytes))
    for i in range(length):
        encrypted[i] = data_bytes[i] ^ ord(otp_content[i])

    # If the OTP page is shorter than data_bytes, the remainder is unencrypted
    for i in range(length, len(data_bytes)):
        encrypted[i] = data_bytes[i]

    return bytes(encrypted)

def decrypt_chunk(encrypted_bytes, otp_content):
    """
    Reverse of encrypt_chunk (XOR is symmetric).
    """
    if len(otp_content) < len(encrypted_bytes):
        length = len(otp_content)
    else:
        length = len(encrypted_bytes)

    decrypted = bytearray(len(encrypted_bytes))
    for i in range(length):
        decrypted[i] = encrypted_bytes[i] ^ ord(otp_content[i])
    for i in range(length, len(encrypted_bytes)):
        decrypted[i] = encrypted_bytes[i]

    return bytes(decrypted)


class OTPVoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Voice Client")


        self.otp_pages = load_otp_pages("otp_cipher.txt")
        self.used_identifiers = load_used_pages("used_pages.txt")


        self.server_frame = tk.Frame(master)
        self.server_frame.pack(padx=10, pady=10)

        tk.Label(self.server_frame, text="Server Host:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.host_entry = tk.Entry(self.server_frame, width=20)
        self.host_entry.grid(row=0, column=1, padx=5, pady=5)
        self.host_entry.insert(0, "127.0.0.1")  # default local

        tk.Label(self.server_frame, text="Server Port:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.port_entry = tk.Entry(self.server_frame, width=20)
        self.port_entry.grid(row=1, column=1, padx=5, pady=5)
        self.port_entry.insert(0, "65432")  # must match otp_voice_server.py

        tk.Label(self.server_frame, text="Your userID:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.user_id_entry = tk.Entry(self.server_frame, width=20)
        self.user_id_entry.grid(row=2, column=1, padx=5, pady=5)
        self.user_id_entry.insert(0, "alice")

        tk.Button(self.server_frame, text="Connect", command=self.connect_to_server).grid(row=3, column=0, columnspan=2, pady=5)

        self.call_frame = tk.Frame(master)
        self.call_frame.pack(padx=10, pady=10)

        tk.Label(self.call_frame, text="Recipient userID:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.recipient_id_entry = tk.Entry(self.call_frame, width=20)
        self.recipient_id_entry.grid(row=0, column=1, padx=5, pady=5)
        self.recipient_id_entry.insert(0, "bob")

        # Start/Stop call buttons
        self.start_call_button = tk.Button(self.call_frame, text="Start Call", command=self.start_call, state=tk.DISABLED)
        self.start_call_button.grid(row=1, column=0, padx=5, pady=5)

        self.stop_call_button = tk.Button(self.call_frame, text="Stop Call", command=self.stop_call, state=tk.DISABLED)
        self.stop_call_button.grid(row=1, column=1, padx=5, pady=5)

        # Status area
        self.log_area = scrolledtext.ScrolledText(master, height=10, width=50)
        self.log_area.pack(padx=10, pady=10)
        self.log_area.config(state=tk.DISABLED)

        self.client_socket = None
        self.server_host = None
        self.server_port = None
        self.user_id = None


        self.p = pyaudio.PyAudio()
        self.stream_in = None
        self.stream_out = None
        self.audio_running = False

        self.RATE = 44100
        self.CHUNK = 1024

    def connect_to_server(self):
        """
        Connect to the TCP server, send userID, and wait for response.
        If successful, enable the call controls.
        """
        self.server_host = self.host_entry.get().strip()
        self.server_port = int(self.port_entry.get().strip())
        self.user_id = self.user_id_entry.get().strip()

        if not self.user_id:
            self.log("Please enter a valid userID.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
            self.client_socket.sendall(self.user_id.encode("utf-8"))
            response = self.client_socket.recv(1024).decode("utf-8")
            if "UserID already taken" in response or "Invalid" in response:
                self.log(f"Server response: {response}")
                self.client_socket.close()
                self.client_socket = None
                return

            self.log(f"Connected to server as '{self.user_id}': {response}")
            self.start_call_button.config(state=tk.NORMAL)

            # Start a thread to listen for incoming audio chunks
            threading.Thread(target=self.receive_chunks, daemon=True).start()

        except Exception as e:
            self.log(f"Connection error: {e}")

    def start_call(self):
        """
        Start capturing audio from mic, encrypting it, and sending to recipient.
        """
        recipient_id = self.recipient_id_entry.get().strip()
        if not recipient_id:
            self.log("Please enter a recipient userID.")
            return

        # Setup audio input (microphone)
        try:
            self.stream_in = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
        except Exception as e:
            self.log(f"Error opening microphone: {e}")
            return

        # Setup audio output (speakers)
        try:
            self.stream_out = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
        except Exception as e:
            self.log(f"Error opening speakers: {e}")
            return

        self.audio_running = True
        self.start_call_button.config(state=tk.DISABLED)
        self.stop_call_button.config(state=tk.NORMAL)

        # Start a thread to continuously capture, encrypt, and send audio
        threading.Thread(target=self.send_chunks, args=(recipient_id,), daemon=True).start()

    def stop_call(self):
        """
        Stop sending/receiving audio.
        """
        self.audio_running = False
        self.stop_call_button.config(state=tk.DISABLED)
        self.start_call_button.config(state=tk.NORMAL)

        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()
            self.stream_out = None

    def send_chunks(self, recipient_id):
        """
        Continuously capture audio from mic, encrypt it with an OTP page, and send to server.
        """
        while self.audio_running:
            try:
                audio_data = self.stream_in.read(self.CHUNK, exception_on_overflow=False)
                # Get an unused OTP page
                otp_identifier, otp_content = get_next_otp_page_linux(self.otp_pages, self.used_identifiers)
                if not otp_identifier or not otp_content:
                    self.log("No more OTP pages available! Stopping call.")
                    self.stop_call()
                    break

                # Encrypt
                encrypted_data = encrypt_chunk(audio_data, otp_content)

                # Build message: "recipientID|<identifier>:<encryptedBytes>"
                # encode the encrypted bytes in a form that can be transmitted as a string.
                encrypted_hex = encrypted_data.hex()
                message = f"{recipient_id}|{otp_identifier}:{encrypted_hex}"

                self.client_socket.sendall(message.encode("utf-8"))

            except Exception as e:
                self.log(f"send_chunks error: {e}")
                break

        self.log("Stopped sending chunks.")

    def receive_chunks(self):
        """
        Continuously receive encrypted audio chunks from the server, decrypt them, and play them.
        Format from server: "senderID|<identifier>:<encryptedHex>"
        """
        while True:
            try:
                data = self.client_socket.recv(8192).decode("utf-8")
                if not data:
                    self.log("Server closed connection.")
                    break

                # If the server can also send text error messages (like "Recipient 'X' not found"),
                # detect if the format is valid or not.
                # Expected valid: "senderID|ABC12345:ab12ef78..." 
                if "|" not in data or ":" not in data:
                    self.log(f"Server says: {data}")
                    continue

                sender_id, payload = data.split("|", 1)
                otp_identifier, encrypted_hex = payload.split(":", 1)

                # Find the OTP content for that identifier
                otp_content = None
                for ident, content in self.otp_pages:
                    if ident == otp_identifier:
                        otp_content = content
                        break

                if not otp_content:
                    self.log(f"Received chunk with unknown OTP identifier {otp_identifier}. Cannot decrypt.")
                    continue

                # Mark the page as used
                save_used_page(otp_identifier)
                self.used_identifiers.add(otp_identifier)

                # Convert hex back to bytes
                encrypted_bytes = bytes.fromhex(encrypted_hex)
                decrypted_bytes = decrypt_chunk(encrypted_bytes, otp_content)

                if self.stream_out:
                    self.stream_out.write(decrypted_bytes)
                else:
                    self.log(f"Received audio from {sender_id}, but no output stream open.")
            except Exception as e:
                self.log(f"receive_chunks error: {e}")
                break

        self.log("Receive thread ended.")
        if self.client_socket:
            self.client_socket.close()
        self.log("Disconnected from server.")
        self.master.quit()

    def log(self, msg):
        """Helper to append text to the scrolled log area."""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.yview(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = OTPVoiceClient(root)
    root.mainloop()
