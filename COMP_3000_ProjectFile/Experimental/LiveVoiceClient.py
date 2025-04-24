import tkinter as tk
from tkinter import ttk, scrolledtext
import socket
import threading
import pyaudio
import fcntl
from pathlib import Path

#OTP Utilities
def load_otp_pages(file_name="otp_cipher.txt"):
    """
    Each line:
      8-char identifier + random data
    Example: ABC12345<thousands_of_random_chars>
    """
    pages = []
    path = Path(file_name)
    if not path.exists():
        return pages
    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if len(line) < 8:
                continue
            identifier = line[:8]
            content = line[8:]
            pages.append((identifier, content))
    return pages

def load_used_pages(file_name="used_pages.txt"):
    path = Path(file_name)
    if not path.exists():
        return set()
    with path.open("r") as f:
        return {line.strip() for line in f}

def save_used_page(identifier, file_name="used_pages.txt"):
    with open(file_name, "a") as f:
        f.write(f"{identifier}\n")

def get_next_otp_page_linux(otp_pages, used_identifiers, lock_file="used_pages.lock"):
    """
    Use file locking on Linux to ensure we don't reuse the same line concurrently.
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
    length = min(len(data_bytes), len(otp_content))
    out = bytearray(len(data_bytes))
    for i in range(length):
        out[i] = data_bytes[i] ^ ord(otp_content[i])
    for i in range(length, len(data_bytes)):
        out[i] = data_bytes[i]
    return bytes(out)

def decrypt_chunk(data_bytes, otp_content):
    #XOR is symmetric
    return encrypt_chunk(data_bytes, otp_content)

# PyAudio Device Helpers
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

#Main GUI Client
class OTPVoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Voice Client (Line-based + PyNgrok)")

        #OTP data
        self.otp_pages = load_otp_pages("otp_cipher.txt")
        self.used_identifiers = load_used_pages("used_pages.txt")

        #PyAudio
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

        #Network
        self.client_socket = None
        self.recv_buffer = ""  

        #Audio config
        self.RATE = 44100
        self.CHUNK = 1024

        #Build GUI
        self.build_gui()

    def build_gui(self):
        #Ngrok info + user ID
        frame_top = tk.Frame(self.master)
        frame_top.pack(padx=10, pady=5)

        tk.Label(frame_top, text="Ngrok Host:").grid(row=0, column=0, sticky="e")
        self.host_entry = tk.Entry(frame_top, width=18)
        self.host_entry.grid(row=0, column=1, padx=5)
        self.host_entry.insert(0, "0.tcp.ngrok.io")  #Example

        tk.Label(frame_top, text="Ngrok Port:").grid(row=1, column=0, sticky="e")
        self.port_entry = tk.Entry(frame_top, width=18)
        self.port_entry.grid(row=1, column=1, padx=5)
        self.port_entry.insert(0, "12345")

        tk.Label(frame_top, text="Your userID:").grid(row=2, column=0, sticky="e")
        self.user_id_entry = tk.Entry(frame_top, width=18)
        self.user_id_entry.grid(row=2, column=1, padx=5)
        self.user_id_entry.insert(0, "alice")

        tk.Button(frame_top, text="Connect", command=self.connect_to_server).grid(row=3, column=0, columnspan=2, pady=5)

        #Device selection
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

        #Call controls
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

        #Log area
        self.log_area = scrolledtext.ScrolledText(self.master, width=60, height=10)
        self.log_area.pack(padx=10, pady=10)
        self.log_area.config(state=tk.DISABLED)

    def log(self, text):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, text + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.yview(tk.END)

    #Networking Methods
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

            #Send the userID + newline
            send_line = user_id + "\n"
            self.client_socket.sendall(send_line.encode("utf-8"))

            #Read response lines in background
            threading.Thread(target=self.receive_thread, daemon=True).start()

            self.log(f"Connected to {host}:{port}, sent userID '{user_id}'")
        except Exception as e:
            self.log(f"Connection error: {e}")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
            return

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

        #Cleanup
        self.log("Disconnected from server.")
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None

        #In case the user was in a call stop it
        if self.audio_running:
            self.stop_call()

    def handle_server_line(self, line):

        if line.startswith("Connected successfully"):
            self.log(line)
            self.start_button.config(state=tk.NORMAL)
            return
        if line.startswith("UserID already taken") or "Invalid userID" in line:
            self.log(line)
            #The server closed the socket
            if self.client_socket:
                self.client_socket.close()
            self.client_socket = None
            return
        if "not found" in line or "Invalid chunk format" in line:
            self.log(f"Server says: {line}")
            return

        if "|" in line and ":" in line:
            sender_id, payload = line.split("|", 1)
            if ":" not in payload:
                self.log(f"Server says: {line}")
                return
            otp_id, enc_hex = payload.split(":", 1)
            self.decrypt_and_play(sender_id, otp_id, enc_hex)
        else:
            self.log(f"Server says: {line}")

    #Audio Methods
    def start_call(self):
        recipient_id = self.recipient_id_entry.get().strip()
        if not recipient_id:
            self.log("Please enter recipient userID.")
            return

        #Open mic
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

        #Open speaker
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

        #Background thread to send audio
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
        Capture from mic, encrypt with an unused OTP page, send line:
          "recipientID|otpID:hexData\n"
        """
        while self.audio_running and self.client_socket:
            try:
                audio_data = self.stream_in.read(self.CHUNK, exception_on_overflow=False)
                otp_id, otp_content = get_next_otp_page_linux(self.otp_pages, self.used_identifiers)
                if not otp_id or not otp_content:
                    self.log("Ran out of OTP pages!")
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

    def decrypt_and_play(self, sender_id, otp_id, enc_hex):
        """
        Find the OTP content for `otp_id`, decrypt, and play the audio.
        """
        otp_content = None
        for ident, content in self.otp_pages:
            if ident == otp_id:
                otp_content = content
                break

        if not otp_content:
            self.log(f"Unknown OTP id '{otp_id}'. Cannot decrypt.")
            return

        #Mark as used
        save_used_page(otp_id)
        self.used_identifiers.add(otp_id)

        encrypted_bytes = bytes.fromhex(enc_hex)
        decrypted = decrypt_chunk(encrypted_bytes, otp_content)

        if self.stream_out:
            self.stream_out.write(decrypted)
        else:
            self.log(f"Received audio from {sender_id}, but no output stream open.")

if __name__ == "__main__":
    root = tk.Tk()
    app = OTPVoiceClient(root)
    root.mainloop()
