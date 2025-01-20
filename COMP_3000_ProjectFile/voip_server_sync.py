import socket
import threading
import pyaudio
from pathlib import Path

########################################
#            OTP Helpers
########################################

def load_otp_pages(file_name="otp_cipher.txt"):
    """
    Reads each line of the OTP file, splitting into:
        (identifier, random_content)
    where 'identifier' is the first 8 chars, 'random_content' is everything after.
    Returns a list of tuples: [(id, content)]
    """
    pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"OTP file '{file_name}' not found.")
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if len(line) < 8:
                continue
            identifier = line[:8]
            content = line[8:]
            pages.append((identifier, content))
    return pages

def get_otp_page_by_id(identifier, pages):
    """
    Given an 8-char identifier and a list of (id, content),
    return the corresponding random_content for that id.
    If not found, returns None.
    """
    for (page_id, content) in pages:
        if page_id == identifier:
            return content
    return None

class OTPStreamer:
    """
    A small helper class to feed chunks of OTP data as needed.
    """
    def __init__(self, otp_bytes):
        self.otp_bytes = otp_bytes
        self.position = 0  # current index into self.otp_bytes
    
    def get_chunk(self, size):
        """Return 'size' bytes from the OTP, advancing the position."""
        if self.position + size > len(self.otp_bytes):
            raise RuntimeError("Ran out of OTP data! No more encryption possible.")
        chunk = self.otp_bytes[self.position : self.position + size]
        self.position += size
        return chunk

def xor_encrypt_decrypt(data_bytes, key_bytes):
    """
    XOR-based encryption/decryption. 
    Since XOR is its own inverse, same function works for both.
    """
    return bytes([d ^ k for d, k in zip(data_bytes, key_bytes)])


########################################
#         Audio Configuration
########################################
CHUNK = 1024              # frames per buffer
FORMAT = pyaudio.paInt16  # 16-bit audio
CHANNELS = 1              # mono
RATE = 16000              # 16kHz sample rate


########################################
#           Server Logic
########################################

class VoiceServerSync:
    def __init__(self, host="0.0.0.0", port=50007, otp_file="otp_cipher.txt"):
        self.host = host
        self.port = port

        # 1) Load all OTP pages
        self.pages = load_otp_pages(otp_file)

        # 2) For testing pick the *first* available page. 
        if not self.pages:
            raise RuntimeError("No valid OTP pages found in file!")
        self.otp_identifier, self.otp_content = self.pages[0]
        
        # Convert random content to raw bytes (UTF-8 assumption)
        self.otp_bytes = self.otp_content.encode("utf-8")

        # separate streamers for incoming vs outgoing audio
        self.otp_streamer_send = OTPStreamer(self.otp_bytes)
        self.otp_streamer_recv = OTPStreamer(self.otp_bytes)

        # Audio setup
        self.audio_interface = pyaudio.PyAudio()
        self.stream_output = self.audio_interface.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK
        )
        self.stream_input = self.audio_interface.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK
        )

        self.client_socket = None
        self.running = True

    def start_server(self):
        print(f"[Server] Starting on {self.host}:{self.port} ...")
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.bind((self.host, self.port))
        server_sock.listen(1)
        print("[Server] Waiting for client to connect...")

        # Accept a single client
        self.client_socket, addr = server_sock.accept()
        print(f"[Server] Client connected from {addr}.")

        # 3) Send the 8-char OTP page ID to the client so it knows which page to use
        try:
            self.client_socket.sendall(self.otp_identifier.encode("utf-8"))
            print(f"[Server] Sent OTP page ID: {self.otp_identifier}")
        except Exception as e:
            print("[Server] Failed to send OTP ID:", e)
            self.cleanup()
            return

        # Start threads for receiving & sending
        threading.Thread(target=self.receive_audio, daemon=True).start()
        threading.Thread(target=self.send_audio, daemon=True).start()

        # Keep main thread alive
        try:
            while self.running:
                pass
        except KeyboardInterrupt:
            print("[Server] Keyboard interrupt -> shutting down.")
        finally:
            self.cleanup()

    def receive_audio(self):
        """Receive encrypted audio, XOR-decrypt with self.otp_streamer_recv, and play."""
        while self.running:
            try:
                data = self.client_socket.recv(CHUNK * 2)  # 2 bytes per frame in int16
                if not data:
                    print("[Server] Client disconnected.")
                    self.running = False
                    break
                # Decrypt
                key_chunk = self.otp_streamer_recv.get_chunk(len(data))
                decrypted = xor_encrypt_decrypt(data, key_chunk)
                self.stream_output.write(decrypted)
            except Exception as e:
                print("[Server] Error receiving audio:", e)
                self.running = False
                break

    def send_audio(self):
        """Capture microphone audio, XOR-encrypt with self.otp_streamer_send, and send."""
        while self.running:
            try:
                audio_data = self.stream_input.read(CHUNK)
                key_chunk = self.otp_streamer_send.get_chunk(len(audio_data))
                encrypted = xor_encrypt_decrypt(audio_data, key_chunk)
                self.client_socket.sendall(encrypted)
            except Exception as e:
                print("[Server] Error sending audio:", e)
                self.running = False
                break

    def cleanup(self):
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        self.stream_output.stop_stream()
        self.stream_output.close()
        self.stream_input.stop_stream()
        self.stream_input.close()
        self.audio_interface.terminate()


if __name__ == "__main__":
    server = VoiceServerSync(host="0.0.0.0", port=50007, otp_file="otp_cipher.txt")
    server.start_server()
