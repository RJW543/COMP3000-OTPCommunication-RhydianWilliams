import tkinter as tk
from tkinter import ttk, scrolledtext
import socket
import threading
import pyaudio
from pathlib import Path
import string

#########################
#       OTP Utils       #
#########################

def load_otp_pages(file_name="otp_cipher.txt"):
    """
    Each line has an 8-char identifier + random OTP data
    Example line: ABC12345<random_data>
    """
    pages = []
    path = Path(file_name)
    if not path.exists():
        return pages
    with path.open("r") as f:
        for line in f:
            line = line.rstrip('\n')
            if len(line) < 8:
                continue
            identifier = line[:8]
            content = line[8:]
            pages.append((identifier, content))
    print(f"Loaded {len(pages)} OTP pages from {path}")
    return pages

def encrypt_chunk(data_bytes, otp_content):
    length = min(len(data_bytes), len(otp_content))
    out = bytearray(len(data_bytes))
    for i in range(length):
        out[i] = data_bytes[i] ^ ord(otp_content[i])
    # If audio chunk is longer than OTP content, just copy the remainder as-is
    for i in range(length, len(data_bytes)):
        out[i] = data_bytes[i]
    return bytes(out)

def decrypt_chunk(data_bytes, otp_content):
    return encrypt_chunk(data_bytes, otp_content)  # XOR is symmetric

#########################
#    PyAudio Helpers    #
#########################

def get_input_devices(p):
    devs = []
    count = p.get_device_count()
    for i in range(count):
        info = p.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            devs.append((i, info.get("name", f"Input {i}")))
    return devs

def get_output_devices(p):
    devs = []
    count = p.get_device_count()
    for i in range(count):
        info = p.get_device_info_by_index(i)
        if info.get("maxOutputChannels", 0) > 0:
            devs.append((i, info.get("name", f"Output {i}")))
    return devs

#########################
#    Main GUI Client    #
#########################

class OTPVoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Simple OTP Voice Client")

        # Load OTP pages and track our next index in memory
        self.otp_pages = load_otp_pages("otp_cipher.txt")
        self.next_otp_index = 0  # We'll increment this as we consume pages

        # PyAudio
        self.p = pyaudio.PyAudio()
        self.input_devices = get_input_devices(self.p)
        self.output_devices = get_output_devices(self.p)
        self.selected_input_var = tk.StringVar()
        self.selected_output_var = tk.StringVar()

        if self.input_devices:
            self.selected_input_var.set(self.input_devices[0][1])
        if self.output_devices:
            self.selected_output_var.set(self.output_devices[0][1])

        self.stream_in = None
        self.stream_out = None
        self.audio_running = False

        # Networking
        self.client_socket = None
        self.recv_buffer = ""

        # Audio config
        self.RATE = 44100
        self.CHUNK = 1024

        # Build GUI
        self.build_gui()

    ###############################
    #        Build the GUI       #
    ###############################

    def build_gui(self):
        # Top frame: Connection info
        frame_top = tk.Frame(self.master)
        frame_top.pack(padx=10, pady=5)

        tk.Label(frame_top, text="Ngrok Host:").grid(row=0, column=0, sticky="e")
        self.host_entry = tk.Entry(frame_top, width=18)
        self.host_entry.grid(row=0, column=1, padx=5)
        self.host_entry.insert(0, "0.tcp.ngrok.io")

        tk.Label(frame_top, text="Ngrok Port:").grid(row=1, column=0, sticky="e")
        self.port_entry = tk.Entry(frame_top, width=18)
        self.port_entry.grid(row=1, column=1, padx=5)
        self.port_entry.insert(0, "12345")

        tk.Label(frame_top, text="Your userID:").grid(row=2, column=0, sticky="e")
        self.user_id_entry = tk.Entry(frame_top, width=18)
        self.user_id_entry.grid(row=2, column=1, padx=5)
        self.user_id_entry.insert(0, "alice")

        tk.Button(frame_top, text="Connect", command=self.connect_to_server).grid(row=3, column=0, columnspan=2, pady=5)

        # Middle frame: Device selection
        frame_dev = tk.Frame(self.master)
        frame_dev.pack(padx=10, pady=5)

        tk.Label(frame_dev, text="Microphone:").grid(row=0, column=0, padx=5, sticky="e")
        in_names = [d[1] for d in self.input_devices]
        self.in_menu = ttk.OptionMenu(frame_dev, self.selected_input_var, self.selected_input_var.get(), *in_names)
        self.in_menu.grid(row=0, column=1, padx=5)

        tk.Label(frame_dev, text="Speaker:").grid(row=1, column=0, padx=5, sticky="e")
        out_names = [d[1] for d in self.output_devices]
        self.out_menu = ttk.OptionMenu(frame_dev, self.selected_output_var, self.selected_output_var.get(), *out_names)
        self.out_menu.grid(row=1, column=1, padx=5)

        # Call controls
        frame_call = tk.Frame(self.master)
        frame_call.pack(padx=10, pady=5)

        tk.Label(frame_call, text="Recipient userID:").grid(row=0, column=0, sticky="e")
        self.recipient_id_entry = tk.Entry(frame_call, width=18)
        self.recipient_id_entry.grid(row=0, column=1, padx=5)
        self.recipient_id_entry.insert(0, "bob")

        self.start_button = tk.Button(frame_call, text="Start Call", command=self.start_call, state=tk.DISABLED)
        self.start_button.grid(row=1, column=0, padx=5, pady=3)

        self.stop_button = tk.Button(frame_call, text="Stop Call", command=self.stop_call, state=tk.DISABLED)
        self.stop_button.grid(row=1, column=1, padx=5, pady=3)

        # Log area
        self.log_area = scrolledtext.ScrolledText(self.master, width=60, height=10)
        self.log_area.pack(padx=10, pady=10)
        self.log_area.config(state=tk.DISABLED)

    def log(self, text):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.yview(tk.END)

    ####################################
    #         Networking Methods       #
    ####################################

    def connect_to_server(self):
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        if not port_str.isdigit():
            self.log("Ngrok port must be numeric.")
            return
        port = int(port_str)
        user_id = self.user_id_entry.get().strip()
        if not user_id:
            self.log("Please enter a valid userID.")
            return

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))

            # Send userID + newline
            send_line = user_id + "\n"
            self.client_socket.sendall(send_line.encode("utf-8"))

            # Listen to server in the background
            threading.Thread(target=self.receive_thread, daemon=True).start()

            self.log(f"Connected to {host}:{port}, sent userID '{user_id}'")
        except Exception as e:
            self.log(f"Connection error: {e}")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None

    def receive_thread(self):
        while True:
            try:
                data = self.client_socket.recv(4096)
                if not data:
                    self.log("Server closed connection.")
                    break
                self.recv_buffer += data.decode("utf-8", errors="replace")

                while "\n" in self.recv_buffer:
                    line, self.recv_buffer = self.recv_buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    self.handle_server_line(line)
            except Exception as e:
                self.log(f"receive_thread error: {e}")
                break

        self.log("Disconnected from server.")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

        # If we were in a call, stop it
        if self.audio_running:
            self.stop_call()

    def handle_server_line(self, line):
        if line.startswith("Connected successfully"):
            self.log(line)
            self.start_button.config(state=tk.NORMAL)
            return
        if line.startswith("UserID already taken") or "Invalid userID" in line:
            self.log(line)
            if self.client_socket:
                self.client_socket.close()
            self.client_socket = None
            return
        if "not found" in line or "Invalid chunk format" in line:
            self.log(f"Server says: {line}")
            return

        # Format: "senderID|otpID:encHex"
        if "|" in line and ":" in line:
            sender_id, payload = line.split("|", 1)
            if ":" not in payload:
                self.log(f"Server says: {line}")
                return
            otp_id, enc_hex = payload.split(":", 1)
            self.decrypt_and_play(sender_id, otp_id, enc_hex)
        else:
            self.log(f"Server says: {line}")

    ####################################
    #           Audio Methods          #
    ####################################

    def start_call(self):
        recipient_id = self.recipient_id_entry.get().strip()
        if not recipient_id:
            self.log("Please enter recipient userID.")
            return

        # Open mic
        try:
            in_dev_idx = None
            for idx, name in self.input_devices:
                if name == self.selected_input_var.get():
                    in_dev_idx = idx
                    break

            self.stream_in = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                input_device_index=in_dev_idx
            )
        except Exception as e:
            self.log(f"Failed to open mic: {e}")
            return

        # Open speaker
        try:
            out_dev_idx = None
            for idx, name in self.output_devices:
                if name == self.selected_output_var.get():
                    out_dev_idx = idx
                    break

            self.stream_out = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
                output_device_index=out_dev_idx
            )
        except Exception as e:
            self.log(f"Failed to open speaker: {e}")
            if self.stream_in:
                self.stream_in.close()
            return

        self.recipient_id = recipient_id
        self.audio_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.log(f"Call started with recipient '{recipient_id}'")

        # Send audio in the background
        threading.Thread(target=self.send_chunks, daemon=True).start()

    def stop_call(self):
        self.audio_running = False
        self.stop_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.NORMAL)
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
        Read mic audio, get next OTP page from memory, encrypt, and send.
        Format: "recipientID|otpID:hexData\n"
        """
        while self.audio_running and self.client_socket:
            try:
                audio_data = self.stream_in.read(self.CHUNK, exception_on_overflow=False)
                # Get next OTP page in memory
                otp_id, otp_content = self.get_next_otp_page()
                if not otp_id:
                    self.log("No more OTP pages left!")
                    self.stop_call()
                    break

                enc_bytes = encrypt_chunk(audio_data, otp_content)
                enc_hex = enc_bytes.hex()
                line = f"{self.recipient_id}|{otp_id}:{enc_hex}\n"
                self.client_socket.sendall(line.encode("utf-8"))
            except Exception as e:
                self.log(f"send_chunks error: {e}")
                break

        self.log("Stopped sending chunks.")

    def get_next_otp_page(self):
        """Return (identifier, content) from in-memory OTP pages, advancing our index."""
        if self.next_otp_index >= len(self.otp_pages):
            return None, None
        ident, content = self.otp_pages[self.next_otp_index]
        self.next_otp_index += 1
        return ident, content

    def decrypt_and_play(self, sender_id, otp_id, enc_hex):
        """
        Find `otp_id` among our in-memory pages. Decrypt and play the audio.
        This is naive: we search linearly each time. (We could store in a dict if we want faster lookups.)
        """
        self.log(f"DEBUG: Received OTP id '{otp_id}' from {sender_id}")

        # Search for this OTP id in memory
        match = next(((c) for (i, c) in self.otp_pages if i == otp_id), None)
        if not match:
            self.log(f"Unknown OTP id '{otp_id}'. Cannot decrypt.")
            return

        try:
            encrypted_bytes = bytes.fromhex(enc_hex)
        except ValueError as e:
            self.log(f"Failed to parse hex data: {e}")
            return

        decrypted = decrypt_chunk(encrypted_bytes, match)

        # If no speaker is open, open it
        if not self.stream_out:
            try:
                out_dev_idx = None
                for idx, name in self.output_devices:
                    if name == self.selected_output_var.get():
                        out_dev_idx = idx
                        break
                self.stream_out = self.p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=self.RATE,
                    output=True,
                    frames_per_buffer=self.CHUNK,
                    output_device_index=out_dev_idx
                )
                self.log("Speaker automatically opened for incoming audio.")
            except Exception as e:
                self.log(f"Failed to open speaker automatically: {e}")
                return

        self.stream_out.write(decrypted)

if __name__ == "__main__":
    root = tk.Tk()
    app = OTPVoiceClient(root)
    root.mainloop()
