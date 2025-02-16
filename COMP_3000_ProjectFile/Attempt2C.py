import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import socket
import threading
import pyaudio
import fcntl
from pathlib import Path

# ---------------------------------------
#    One-Time Pad (OTP) Helper Functions
# ---------------------------------------
def load_otp_pages(file_name="otp_cipher.txt"):
    """
    Loads each line of form:
        8-char identifier + random data
    Example line:
        ABC12345<lots_of_random_bytes...>
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
    Returns a set of OTP identifiers that have already been used
    so we don't reuse them (which breaks OTP security).
    """
    path = Path(file_name)
    if not path.exists():
        return set()
    with path.open("r") as f:
        return {line.strip() for line in f}

def save_used_page(identifier, file_name="used_pages.txt"):
    """
    Mark a given OTP identifier as used.
    """
    with open(file_name, "a") as f:
        f.write(f"{identifier}\n")

def get_next_otp_page_linux(otp_pages, used_identifiers, lock_file="used_pages.lock"):
    """
    Retrieves the next unused OTP page from `otp_pages`.
    We use a file lock to ensure single-process usage at a time (Linux only).
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
    XOR each audio byte with the corresponding character in `otp_content`.
    If OTP is shorter, the remainder is unencrypted (just a demo).
    """
    length = min(len(data_bytes), len(otp_content))
    out = bytearray(len(data_bytes))
    for i in range(length):
        out[i] = data_bytes[i] ^ ord(otp_content[i])
    for i in range(length, len(data_bytes)):
        out[i] = data_bytes[i]
    return bytes(out)

def decrypt_chunk(data_bytes, otp_content):
    """
    XOR is symmetric, so the same operation decrypts.
    """
    return encrypt_chunk(data_bytes, otp_content)

# ---------------------------------------
#  PyAudio Device Enumeration Functions
# ---------------------------------------
def get_input_devices(p):
    """
    Return a list of (index, device_name) for devices with maxInputChannels > 0
    """
    devices = []
    count = p.get_device_count()
    for i in range(count):
        dev_info = p.get_device_info_by_index(i)
        if dev_info.get('maxInputChannels', 0) > 0:
            name = dev_info.get('name', f"Device {i}")
            devices.append((i, name))
    return devices

def get_output_devices(p):
    """
    Return a list of (index, device_name) for devices with maxOutputChannels > 0
    """
    devices = []
    count = p.get_device_count()
    for i in range(count):
        dev_info = p.get_device_info_by_index(i)
        if dev_info.get('maxOutputChannels', 0) > 0:
            name = dev_info.get('name', f"Device {i}")
            devices.append((i, name))
    return devices

# ---------------------------------------
#         Main GUI Client Class
# ---------------------------------------
class OTPVoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Voice Client (ngrok + Device Select)")

        # ---- OTP Setup ----
        self.otp_pages = load_otp_pages("otp_cipher.txt")
        self.used_identifiers = load_used_pages("used_pages.txt")

        # ---- PyAudio Setup ----
        self.p = pyaudio.PyAudio()
        self.input_devices = get_input_devices(self.p)
        self.output_devices = get_output_devices(self.p)

        self.selected_input_var = tk.StringVar()
        self.selected_output_var = tk.StringVar()

        # Default to the first device if exists
        if self.input_devices:
            self.selected_input_var.set(self.input_devices[0][1])
        if self.output_devices:
            self.selected_output_var.set(self.output_devices[0][1])

        # Streams
        self.stream_in = None
        self.stream_out = None
        self.audio_running = False

        # Connection / Socket
        self.client_socket = None

        # Audio / Network constants
        self.RATE = 44100
        self.CHUNK = 1024

        # ---- Build GUI ----
        self.build_gui()

    def build_gui(self):
        # Frame for ngrok + user ID
        ngrok_frame = tk.Frame(self.master)
        ngrok_frame.pack(padx=10, pady=5)

        tk.Label(ngrok_frame, text="Ngrok Host:").grid(row=0, column=0, sticky="e", padx=5, pady=3)
        self.ngrok_host_entry = tk.Entry(ngrok_frame, width=20)
        self.ngrok_host_entry.grid(row=0, column=1, padx=5, pady=3)
        self.ngrok_host_entry.insert(0, "0.tcp.ngrok.io")

        tk.Label(ngrok_frame, text="Ngrok Port:").grid(row=1, column=0, sticky="e", padx=5, pady=3)
        self.ngrok_port_entry = tk.Entry(ngrok_frame, width=20)
        self.ngrok_port_entry.grid(row=1, column=1, padx=5, pady=3)
        self.ngrok_port_entry.insert(0, "12345")

        tk.Label(ngrok_frame, text="Your userID:").grid(row=2, column=0, sticky="e", padx=5, pady=3)
        self.user_id_entry = tk.Entry(ngrok_frame, width=20)
        self.user_id_entry.grid(row=2, column=1, padx=5, pady=3)
        self.user_id_entry.insert(0, "alice")

        tk.Button(ngrok_frame, text="Connect", command=self.connect_to_server).grid(row=3, column=0, columnspan=2, pady=5)

        # Frame for device selection
        device_frame = tk.Frame(self.master)
        device_frame.pack(padx=10, pady=5)

        tk.Label(device_frame, text="Microphone:").grid(row=0, column=0, sticky="e", padx=5)
        input_choices = [d[1] for d in self.input_devices]
        self.input_menu = ttk.OptionMenu(device_frame, self.selected_input_var,
                                         self.selected_input_var.get(), *input_choices)
        self.input_menu.grid(row=0, column=1, padx=5)

        tk.Label(device_frame, text="Speaker:").grid(row=1, column=0, sticky="e", padx=5)
        output_choices = [d[1] for d in self.output_devices]
        self.output_menu = ttk.OptionMenu(device_frame, self.selected_output_var,
                                          self.selected_output_var.get(), *output_choices)
        self.output_menu.grid(row=1, column=1, padx=5)

        # Frame for call controls
        call_frame = tk.Frame(self.master)
        call_frame.pack(padx=10, pady=5)

        tk.Label(call_frame, text="Recipient userID:").grid(row=0, column=0, sticky="e", padx=5)
        self.recipient_id_entry = tk.Entry(call_frame, width=20)
        self.recipient_id_entry.grid(row=0, column=1, padx=5)
        self.recipient_id_entry.insert(0, "bob")

        self.start_call_button = tk.Button(call_frame, text="Start Call", command=self.start_call, state=tk.DISABLED)
        self.start_call_button.grid(row=1, column=0, padx=5, pady=3)

        self.stop_call_button = tk.Button(call_frame, text="Stop Call", command=self.stop_call, state=tk.DISABLED)
        self.stop_call_button.grid(row=1, column=1, padx=5, pady=3)

        # Log area
        self.log_area = scrolledtext.ScrolledText(self.master, height=10, width=60)
        self.log_area.pack(padx=10, pady=10)
        self.log_area.config(state=tk.DISABLED)

    # ---------------
    #  Network Logic
    # ---------------
    def connect_to_server(self):
        host = self.ngrok_host_entry.get().strip()
        port_str = self.ngrok_port_entry.get().strip()

        if not port_str.isdigit():
            self.log("Ngrok port must be numeric.")
            return

        port = int(port_str)
        user_id = self.user_id_entry.get().strip()
        if not user_id:
            self.log("Please provide a valid userID.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            # Send userID
            self.client_socket.sendall(user_id.encode("utf-8"))

            response = self.client_socket.recv(1024).decode("utf-8")
            if "already taken" in response or "Invalid" in response:
                self.log(f"Server: {response}")
                self.client_socket.close()
                self.client_socket = None
                return

            self.log(f"Connected to {host}:{port} as '{user_id}'. Server says: {response}")
            self.start_call_button.config(state=tk.NORMAL)

            # Start a thread to receive chunks
            threading.Thread(target=self.receive_chunks, daemon=True).start()

        except Exception as e:
            self.log(f"Connection error: {e}")

    def start_call(self):
        """
        Select mic/speaker devices, open streams, and begin sending audio.
        """
        recipient_id = self.recipient_id_entry.get().strip()
        if not recipient_id:
            self.log("Please enter recipient userID.")
            return

        # Resolve device indexes from selection
        input_dev_index = None
        for idx, name in self.input_devices:
            if name == self.selected_input_var.get():
                input_dev_index = idx
                break

        output_dev_index = None
        for idx, name in self.output_devices:
            if name == self.selected_output_var.get():
                output_dev_index = idx
                break

        # Open microphone
        try:
            self.stream_in = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                input_device_index=input_dev_index
            )
        except Exception as e:
            self.log(f"Failed to open mic ({self.selected_input_var.get()}): {e}")
            return

        # Open speaker
        try:
            self.stream_out = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
                output_device_index=output_dev_index
            )
        except Exception as e:
            self.log(f"Failed to open speaker ({self.selected_output_var.get()}): {e}")
            if self.stream_in:
                self.stream_in.close()
            return

        self.audio_running = True
        self.start_call_button.config(state=tk.DISABLED)
        self.stop_call_button.config(state=tk.NORMAL)
        self.log(f"Call started. Sending to recipient: {recipient_id}")

        # Background thread to send audio
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

        self.log("Call stopped.")

    def send_chunks(self, recipient_id):
        """
        Continuously read from mic, encrypt with a new OTP page, and send to server.
        """
        while self.audio_running and self.client_socket:
            try:
                # Capture audio chunk
                audio_data = self.stream_in.read(self.CHUNK, exception_on_overflow=False)
                # Get an unused OTP page
                otp_id, otp_content = get_next_otp_page_linux(self.otp_pages, self.used_identifiers)
                if not otp_id or not otp_content:
                    self.log("No more OTP pages! Ending call.")
                    self.stop_call()
                    break

                encrypted_bytes = encrypt_chunk(audio_data, otp_content)
                # Convert to hex for safe transmission
                enc_hex = encrypted_bytes.hex()

                # Format: "recipientID|otpID:encHex"
                message = f"{recipient_id}|{otp_id}:{enc_hex}"
                self.client_socket.sendall(message.encode("utf-8"))

            except Exception as e:
                self.log(f"send_chunks error: {e}")
                break

        self.log("Stopped sending chunks.")

    def receive_chunks(self):
        """
        Continuously read from server: "senderID|otpID:encHex"
        Decrypt and play on speaker if a call is active.
        """
        while True:
            try:
                if not self.client_socket:
                    break
                data = self.client_socket.recv(8192).decode("utf-8")
                if not data:
                    self.log("Server closed connection.")
                    break

                # Could be an error message or a valid chunk
                if "|" not in data or ":" not in data:
                    self.log(f"Server says: {data}")
                    continue

                sender_id, payload = data.split("|", 1)
                otp_id, enc_hex = payload.split(":", 1)

                # Find matching OTP content
                otp_content = None
                for ident, content in self.otp_pages:
                    if ident == otp_id:
                        otp_content = content
                        break

                if not otp_content:
                    self.log(f"Unknown OTP ID {otp_id}. Cannot decrypt.")
                    continue

                # Mark it used
                save_used_page(otp_id)
                self.used_identifiers.add(otp_id)

                # Decrypt
                encrypted_bytes = bytes.fromhex(enc_hex)
                decrypted_audio = decrypt_chunk(encrypted_bytes, otp_content)

                if self.stream_out:
                    self.stream_out.write(decrypted_audio)
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
        """
        Append text to the scrolled log area.
        """
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.yview(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    app = OTPVoiceClient(root)
    root.mainloop()
