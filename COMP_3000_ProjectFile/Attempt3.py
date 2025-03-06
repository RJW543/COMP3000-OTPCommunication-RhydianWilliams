import tkinter as tk
from tkinter import ttk, messagebox
import socket
import threading
import pyaudio
import sys
import traceback

from urllib.parse import urlparse

# For ngrok tunneling
from pyngrok import ngrok


CHUNK = 1024        # Number of audio frames per buffer
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000        # Sample rate
PORT = 50007        

class VoiceChatGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Pi-to-Pi Voice Chat (Ngrok)")

        self.mode = tk.StringVar(value="server")   # "server" or "client"
        self.peer_addr = tk.StringVar(value="")    # Could be IP address or Ngrok URL

        self.server_socket = None
        self.client_socket = None
        self.connected = False
        self.stop_threads = False  # Flag to stop audio threads

        self.audio_interface = pyaudio.PyAudio()
        self.stream_out = None
        self.stream_in = None

        self.ngrok_tunnel = None

        # Build the GUI
        self.create_widgets()

    def create_widgets(self):
        frm = ttk.Frame(self.master, padding=10)
        frm.grid()

        # Mode (Server/Client)
        ttk.Label(frm, text="Mode:").grid(column=0, row=0, sticky="W")
        ttk.Radiobutton(frm, text="Server", variable=self.mode, value="server").grid(column=1, row=0, sticky="W")
        ttk.Radiobutton(frm, text="Client", variable=self.mode, value="client").grid(column=2, row=0, sticky="W")

        # Peer Address (IP or ngrok URL)
        ttk.Label(frm, text="Peer Address:").grid(column=0, row=1, sticky="W")
        ttk.Entry(frm, textvariable=self.peer_addr, width=30).grid(column=1, row=1, columnspan=2, sticky="W")

        # Start button
        ttk.Button(frm, text="Start", command=self.start_action).grid(column=0, row=2, pady=10, sticky="W")

        # Status label
        self.status_label = ttk.Label(frm, text="Not connected.")
        self.status_label.grid(column=1, row=2, columnspan=2, pady=10, sticky="W")

    def start_action(self):
        """Handles the Start button press."""
        selected_mode = self.mode.get()
        if selected_mode == "server":
            # Start the server (which also starts ngrok tunnel)
            self.update_status("Starting server...")
            t = threading.Thread(target=self.start_server, daemon=True)
            t.start()
        else:
            # Start the client
            if not self.peer_addr.get():
                messagebox.showerror("Error", "Please enter the Server's Ngrok URL or IP address.")
                return
            self.update_status("Connecting to server...")
            t = threading.Thread(target=self.start_client, daemon=True)
            t.start()

    def start_server(self):
        """Set up local server socket, expose via ngrok, and wait for client."""
        try:
            # 1) Create local TCP server
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("0.0.0.0", PORT))
            self.server_socket.listen(1)

            # 2) Create an ngrok tunnel for the chosen port
            self.ngrok_tunnel = ngrok.connect(PORT, "tcp")
            public_url = self.ngrok_tunnel.public_url  

            self.update_status(f"Server listening.\nPublic ngrok URL:\n{public_url}")

            # 3) Wait for one client to connect
            conn, addr = self.server_socket.accept()
            self.update_status(f"Client connected from {addr}")
            self.client_socket = conn
            self.connected = True

            # 4) Start audio streaming in both directions
            self.start_audio_streams()

        except Exception as e:
            traceback.print_exc()
            self.update_status(f"Server error: {e}")

    def start_client(self):
        """Connect to the server as client (resolving possibly a ngrok TCP URL)."""
        try:
            host, port = self.parse_address(self.peer_addr.get())

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.update_status("Connected to server!")
            self.connected = True

            # Start audio streaming
            self.start_audio_streams()

        except Exception as e:
            traceback.print_exc()
            self.update_status(f"Client error: {e}")

    def start_audio_streams(self):
        """Initialize PyAudio streams and launch send/receive threads."""
        try:
            # Output stream (speaker/headphones)
            self.stream_out = self.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK
            )

            # Input stream (microphone)
            self.stream_in = self.audio_interface.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )

            self.stop_threads = False
            threading.Thread(target=self.send_audio, daemon=True).start()
            threading.Thread(target=self.receive_audio, daemon=True).start()

        except Exception as e:
            traceback.print_exc()
            self.update_status(f"Audio error: {e}")

    def send_audio(self):
        """Continuously read from microphone and send to peer."""
        while not self.stop_threads and self.connected:
            try:
                data = self.stream_in.read(CHUNK, exception_on_overflow=False)
                self.client_socket.sendall(data)
            except (OSError, socket.error):
                break
            except Exception as e:
                print("Error in send_audio:", e)
                break
        self.cleanup()

    def receive_audio(self):
        """Continuously receive audio from peer and play it."""
        while not self.stop_threads and self.connected:
            try:
                data = self.client_socket.recv(CHUNK)
                if not data:
                    break
                self.stream_out.write(data)
            except (OSError, socket.error):
                break
            except Exception as e:
                print("Error in receive_audio:", e)
                break
        self.cleanup()

    def parse_address(self, address_str):
        """
        Parse an address string which could be:
         - "tcp://0.tcp.ngrok.io:12345"
         - "0.tcp.ngrok.io:12345"
         - "192.168.1.50:50007"
        Returns (host, port).
        """
        if "://" in address_str:
            url = urlparse(address_str)
            host = url.hostname
            port = url.port
        else:
            # No scheme, maybe "hostname:port"
            parts = address_str.split(":")
            if len(parts) != 2:
                raise ValueError("Invalid address format. Must be host:port or tcp://host:port")
            host = parts[0]
            port = int(parts[1])
        return host, port

    def update_status(self, message):
        """Update the status label in a thread-safe manner."""
        def _update():
            self.status_label.config(text=message)
        self.master.after(0, _update)

    def cleanup(self):
        """Clean up sockets and PyAudio streams."""
        self.stop_threads = True
        self.connected = False

        if self.stream_in:
            try:
                self.stream_in.stop_stream()
                self.stream_in.close()
            except:
                pass
            self.stream_in = None

        if self.stream_out:
            try:
                self.stream_out.stop_stream()
                self.stream_out.close()
            except:
                pass
            self.stream_out = None

        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        # Optionally kill the ngrok tunnel if it exists
        if self.ngrok_tunnel:
            try:
                ngrok.disconnect(self.ngrok_tunnel.public_url)
                self.ngrok_tunnel = None
            except:
                pass

        self.update_status("Connection closed.")

    def on_closing(self):
        """Handle window closure."""
        self.cleanup()
        self.audio_interface.terminate()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = VoiceChatGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
