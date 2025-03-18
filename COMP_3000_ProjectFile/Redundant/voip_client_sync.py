import socket
import threading
import pyaudio
from pathlib import Path

########################################
#            OTP Helpers
########################################

def load_otp_pages(file_name="otp_cipher.txt"):
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
    """Return the random content from pages matching the given identifier."""
    for page_id, content in pages:
        if page_id == identifier:
            return content
    return None

class OTPStreamer:
    def __init__(self, otp_bytes):
        self.otp_bytes = otp_bytes
        self.position = 0
    
    def get_chunk(self, size):
        if self.position + size > len(self.otp_bytes):
            raise RuntimeError("Ran out of OTP data! No more encryption possible.")
        chunk = self.otp_bytes[self.position : self.position + size]
        self.position += size
        return chunk

def xor_encrypt_decrypt(data_bytes, key_bytes):
    return bytes([d ^ k for d, k in zip(data_bytes, key_bytes)])


########################################
#         Audio Configuration
########################################
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000


########################################
#           Client Logic
########################################

class VoiceClientSync:
    def __init__(self, server_host="127.0.0.1", server_port=50007, otp_file="otp_cipher.txt"):
        self.server_host = server_host
        self.server_port = server_port
        self.otp_file = otp_file
        
        # Pre-load all pages wait to receive the chosen ID from server
        self.pages = load_otp_pages(otp_file)
        
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

        # set after getting the ID from the server
        self.otp_streamer_send = None
        self.otp_streamer_recv = None

    def start_client(self):
        print(f"[Client] Connecting to server {self.server_host}:{self.server_port}...")
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((self.server_host, self.server_port))
        print("[Client] Connected to server.")

        # 1) Immediately receive the 8-char ID from the server
        otp_id = self.client_socket.recv(8).decode("utf-8")  # block until exactly 8 bytes
        if not otp_id:
            print("[Client] Failed to receive OTP page ID.")
            self.cleanup()
            return
        print(f"[Client] Received OTP page ID: {otp_id}")

        # 2) Find the matching page in the OTP file
        otp_content = get_otp_page_by_id(otp_id, self.pages)
        if not otp_content:
            print("[Client] Could not find matching OTP page in local file. Closing.")
            self.cleanup()
            return

        # 3) Create OTP streamers for sending & receiving
        otp_bytes = otp_content.encode("utf-8")
        self.otp_streamer_send = OTPStreamer(otp_bytes)
        self.otp_streamer_recv = OTPStreamer(otp_bytes)

        # Start threads for receiving & sending audio
        threading.Thread(target=self.receive_audio, daemon=True).start()
        threading.Thread(target=self.send_audio, daemon=True).start()

        # Keep the main thread alive
        try:
            while self.running:
                pass
        except KeyboardInterrupt:
            print("[Client] Keyboard interrupt -> shutting down.")
        finally:
            self.cleanup()

    def receive_audio(self):
        """Receive encrypted audio, XOR-decrypt, and play."""
        while self.running:
            try:
                data = self.client_socket.recv(CHUNK * 2)
                if not data:
                    print("[Client] Server disconnected.")
                    self.running = False
                    break
                key_chunk = self.otp_streamer_recv.get_chunk(len(data))
                decrypted = xor_encrypt_decrypt(data, key_chunk)
                self.stream_output.write(decrypted)
            except Exception as e:
                print("[Client] Error receiving audio:", e)
                self.running = False
                break

    def send_audio(self):
        """Capture mic audio, XOR-encrypt, and send."""
        while self.running:
            try:
                audio_data = self.stream_input.read(CHUNK)
                key_chunk = self.otp_streamer_send.get_chunk(len(audio_data))
                encrypted = xor_encrypt_decrypt(audio_data, key_chunk)
                self.client_socket.sendall(encrypted)
            except Exception as e:
                print("[Client] Error sending audio:", e)
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
    client = VoiceClientSync(server_host="127.0.0.1", server_port=50007, otp_file="otp_cipher.txt")
    client.start_client()
