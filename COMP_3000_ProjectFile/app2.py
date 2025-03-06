import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import socket
import pyaudio
from pyngrok import ngrok

################################
#      Minimal Relay Server    #
################################

def handle_relay(from_sock, to_sock):
    """Continuously forward data from `from_sock` to `to_sock` until one side closes."""
    try:
        while True:
            data = from_sock.recv(4096)
            if not data:
                break
            to_sock.sendall(data)
    except:
        pass
    finally:
        to_sock.close()
        from_sock.close()

def run_server(server_gui):
    """
    Wait for two clients, then forward data in both directions.
    Uses pyngrok to expose the local socket. Runs until clients disconnect.
    """
    host = "0.0.0.0"
    port = 5000

    # Open pyngrok TCP tunnel
    public_url = ngrok.connect(port, "tcp")
    server_gui.log(f"[SERVER] Ngrok tunnel: {public_url.public_url}")
    server_gui.public_url_var.set(public_url.public_url)

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((host, port))
    server_sock.listen(2)

    server_gui.log(f"[SERVER] Listening on {host}:{port}...")

    try:
        # Accept two clients
        server_gui.log("[SERVER] Waiting for first client...")
        c1, addr1 = server_sock.accept()
        server_gui.log(f"[SERVER] First client connected from {addr1}")

        server_gui.log("[SERVER] Waiting for second client...")
        c2, addr2 = server_sock.accept()
        server_gui.log(f"[SERVER] Second client connected from {addr2}")

        # Launch two threads to relay data
        t1 = threading.Thread(target=handle_relay, args=(c1, c2), daemon=True)
        t2 = threading.Thread(target=handle_relay, args=(c2, c1), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    except Exception as e:
        server_gui.log(f"[SERVER] Error: {e}")
    finally:
        server_sock.close()
        server_gui.log("[SERVER] Stopped.")

################################
#      Unencrypted Client      #
################################

class UnencryptedVoiceClient:
    """
    Minimal client that:
      1) Connects to a TCP relay (public via pyngrok).
      2) Records mic audio in chunks and sends raw data.
      3) Receives raw data and plays it to speaker.
      (No encryption/XOR.)
    """
    def __init__(self, log_callback):
        self.log_callback = log_callback
        self.socket = None
        self.rate = 44100
        self.chunk_size = 1024

        self.running = False

        # PyAudio
        self.p = pyaudio.PyAudio()
        self.stream_in = None
        self.stream_out = None

        # Device indices
        self.in_dev_idx = None
        self.out_dev_idx = None

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def connect(self, host, port):
        self.log(f"[CLIENT] Connecting to {host}:{port}...")
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, int(port)))
            self.log("[CLIENT] Connected.")
            return True
        except Exception as e:
            self.log(f"[CLIENT] Connect error: {e}")
            return False

    def set_devices(self, in_dev_idx, out_dev_idx):
        """Which input/output device indices to use."""
        self.in_dev_idx = in_dev_idx
        self.out_dev_idx = out_dev_idx

    def start_audio(self):
        """Open mic & speaker, start send/recv loops."""
        if not self.socket:
            self.log("[CLIENT] Socket not connected.")
            return

        # Open mic
        try:
            self.stream_in = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=self.in_dev_idx
            )
        except Exception as e:
            self.log(f"[CLIENT] Failed to open mic: {e}")
            return

        # Open speaker
        try:
            self.stream_out = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk_size,
                output_device_index=self.out_dev_idx
            )
        except Exception as e:
            self.log(f"[CLIENT] Failed to open speaker: {e}")
            if self.stream_in:
                self.stream_in.close()
            return

        self.running = True
        self.log("[CLIENT] Audio started.")
        threading.Thread(target=self.send_loop, daemon=True).start()
        threading.Thread(target=self.recv_loop, daemon=True).start()

    def send_loop(self):
        """Read mic data and send raw bytes."""
        while self.running:
            try:
                audio_data = self.stream_in.read(self.chunk_size, exception_on_overflow=False)
                self.socket.sendall(audio_data)
            except Exception as e:
                self.log(f"[CLIENT] send_loop error: {e}")
                break
        self.log("[CLIENT] send_loop exited.")

    def recv_loop(self):
        """Receive raw data and play."""
        while self.running:
            try:
                data = self.socket.recv(self.chunk_size)
                if not data:
                    break
                self.stream_out.write(data)
            except Exception as e:
                self.log(f"[CLIENT] recv_loop error: {e}")
                break
        self.log("[CLIENT] recv_loop exited.")
        self.stop()

    def stop(self):
        self.running = False
        if self.stream_in:
            self.stream_in.close()
            self.stream_in = None
        if self.stream_out:
            self.stream_out.close()
            self.stream_out = None
        if self.socket:
            self.socket.close()
            self.socket = None
        self.p.terminate()
        self.log("[CLIENT] Stopped.")

################################
#          Main GUI            #
################################

class LogMixin:
    """Utility mixin to provide a .log_area and .log() method."""
    def log(self, msg):
        self.log_area.config(state=tk.NORMAL)
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.config(state=tk.DISABLED)
        self.log_area.yview(tk.END)

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PyNgrok TCP Relay + Unencrypted Voice Chat")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Server tab
        self.server_frame = ServerFrame(self.notebook)
        self.notebook.add(self.server_frame, text="Server")

        # Client tab
        self.client_frame = ClientFrame(self.notebook)
        self.notebook.add(self.client_frame, text="Client")


class ServerFrame(tk.Frame, LogMixin):
    def __init__(self, parent):
        super().__init__(parent)
        self.server_thread = None
        self.running = False
        self.build_ui()

    def build_ui(self):
        frame_top = tk.Frame(self)
        frame_top.pack(pady=5)

        self.start_btn = tk.Button(frame_top, text="Start Server", command=self.start_server)
        self.start_btn.grid(row=0, column=0, padx=10)

        self.stop_btn = tk.Button(frame_top, text="Stop Server", command=self.stop_server, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=10)

        tk.Label(frame_top, text="Public URL:").grid(row=1, column=0, sticky="e")
        self.public_url_var = tk.StringVar()
        self.public_url_label = tk.Label(frame_top, textvariable=self.public_url_var, fg="blue")
        self.public_url_label.grid(row=1, column=1, sticky="w")

        self.log_area = scrolledtext.ScrolledText(self, width=60, height=10)
        self.log_area.pack(pady=10)
        self.log_area.config(state=tk.DISABLED)

    def start_server(self):
        if self.running:
            return
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.log("[SERVER] Starting in background thread...")
        self.server_thread = threading.Thread(target=run_server, args=(self,), daemon=True)
        self.server_thread.start()

    def stop_server(self):
        self.log("[SERVER] Manual stop: the server stops after current session ends.")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.running = False
        # We can't forcibly kill accept() easily. We'll rely on the user closing the app or
        # letting the server finish once the clients disconnect.

################################
#         Client Frame         #
################################

class ClientFrame(tk.Frame, LogMixin):
    def __init__(self, parent):
        super().__init__(parent)
        self.client = None

        # PyAudio device lists
        self.p = pyaudio.PyAudio()
        self.input_devs = []
        self.output_devs = []
        self.build_ui()

    def build_ui(self):
        # Connection info
        frame_conn = tk.Frame(self)
        frame_conn.pack(padx=10, pady=5)

        tk.Label(frame_conn, text="Host:").grid(row=0, column=0, sticky="e")
        self.host_entry = tk.Entry(frame_conn, width=20)
        self.host_entry.grid(row=0, column=1, padx=5)
        self.host_entry.insert(0, "0.tcp.ngrok.io")  # Example default

        tk.Label(frame_conn, text="Port:").grid(row=1, column=0, sticky="e")
        self.port_entry = tk.Entry(frame_conn, width=20)
        self.port_entry.grid(row=1, column=1, padx=5)
        self.port_entry.insert(0, "12345")  # Example default

        self.connect_btn = tk.Button(frame_conn, text="Connect", command=self.connect_to_server)
        self.connect_btn.grid(row=2, column=0, columnspan=2, pady=5)

        # Audio device selection
        frame_dev = tk.Frame(self)
        frame_dev.pack(padx=10, pady=5)
        self.update_audio_devices()

        tk.Label(frame_dev, text="Microphone:").grid(row=0, column=0, sticky="e")
        self.in_var = tk.StringVar(self)
        if self.input_devs:
            self.in_var.set(self.input_devs[0][1])
        self.in_menu = ttk.OptionMenu(frame_dev, self.in_var, self.in_var.get(), *[d[1] for d in self.input_devs])
        self.in_menu.grid(row=0, column=1, padx=5)

        tk.Label(frame_dev, text="Speaker:").grid(row=1, column=0, sticky="e")
        self.out_var = tk.StringVar(self)
        if self.output_devs:
            self.out_var.set(self.output_devs[0][1])
        self.out_menu = ttk.OptionMenu(frame_dev, self.out_var, self.out_var.get(), *[d[1] for d in self.output_devs])
        self.out_menu.grid(row=1, column=1, padx=5)

        # Call controls
        frame_call = tk.Frame(self)
        frame_call.pack(padx=10, pady=5)

        self.start_call_btn = tk.Button(frame_call, text="Start Call", command=self.start_call, state=tk.DISABLED)
        self.start_call_btn.grid(row=0, column=0, padx=5)

        self.stop_call_btn = tk.Button(frame_call, text="Stop Call", command=self.stop_call, state=tk.DISABLED)
        self.stop_call_btn.grid(row=0, column=1, padx=5)

        # Log area
        self.log_area = scrolledtext.ScrolledText(self, width=60, height=10)
        self.log_area.pack(padx=10, pady=10)
        self.log_area.config(state=tk.DISABLED)

    def update_audio_devices(self):
        """Scan PyAudio devices for input/output."""
        self.input_devs = []
        self.output_devs = []
        count = self.p.get_device_count()
        for i in range(count):
            info = self.p.get_device_info_by_index(i)
            name = info.get("name", f"Device {i}")
            if info.get("maxInputChannels", 0) > 0:
                self.input_devs.append((i, name))
            if info.get("maxOutputChannels", 0) > 0:
                self.output_devs.append((i, name))

    def connect_to_server(self):
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        if not port_str.isdigit():
            self.log("[CLIENT] Port must be numeric.")
            return

        port = int(port_str)
        self.client = UnencryptedVoiceClient(log_callback=self.log)
        success = self.client.connect(host, port)
        if success:
            self.connect_btn.config(state=tk.DISABLED)
            self.start_call_btn.config(state=tk.NORMAL)

    def start_call(self):
        if not self.client:
            self.log("[CLIENT] Not connected.")
            return

        # Find device indices based on user selection
        in_dev_idx = None
        out_dev_idx = None

        for idx, name in self.input_devs:
            if name == self.in_var.get():
                in_dev_idx = idx
                break

        for idx, name in self.output_devs:
            if name == self.out_var.get():
                out_dev_idx = idx
                break

        self.client.set_devices(in_dev_idx, out_dev_idx)
        self.client.start_audio()
        self.start_call_btn.config(state=tk.DISABLED)
        self.stop_call_btn.config(state=tk.NORMAL)

    def stop_call(self):
        if self.client:
            self.client.stop()
        self.start_call_btn.config(state=tk.DISABLED)
        self.stop_call_btn.config(state=tk.DISABLED)
        self.connect_btn.config(state=tk.NORMAL)


def main():
    app = MainApp()
    app.mainloop()

if __name__ == "__main__":
    main()
