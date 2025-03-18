import tkinter as tk
import pyaudio
import socket
import threading
import queue
import sys

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class VoiceServer:
    def __init__(self, master):
        self.master = master
        self.master.title("Voice Server")

        self.server_socket = None
        self.client_socket = None
        self.audio = pyaudio.PyAudio()

        self.input_device_index = None
        self.output_device_index = None
        self.stream_in = None
        self.stream_out = None

        self.is_server_running = False
        self.is_streaming = False

        self.input_device_var = tk.StringVar()
        self.output_device_var = tk.StringVar()
        self.port_var = tk.StringVar(value="5000")

        self.create_widgets()

    def create_widgets(self):
        # Label and dropdown for input device
        tk.Label(self.master, text="Input Device:").grid(row=0, column=0, padx=5, pady=5)
        self.input_device_menu = tk.OptionMenu(self.master, self.input_device_var, *self.get_input_devices())
        self.input_device_menu.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Label and dropdown for output device
        tk.Label(self.master, text="Output Device:").grid(row=1, column=0, padx=5, pady=5)
        self.output_device_menu = tk.OptionMenu(self.master, self.output_device_var, *self.get_output_devices())
        self.output_device_menu.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Label and entry for port
        tk.Label(self.master, text="Port:").grid(row=2, column=0, padx=5, pady=5)
        tk.Entry(self.master, textvariable=self.port_var).grid(row=2, column=1, padx=5, pady=5)

        # Start and Stop server buttons
        self.start_button = tk.Button(self.master, text="Start Server", command=self.start_server)
        self.start_button.grid(row=3, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(self.master, text="Stop Server", command=self.stop_server, state="disabled")
        self.stop_button.grid(row=3, column=1, padx=5, pady=5)

    def get_input_devices(self):
        """
        Returns a list of device names that have input channels.
        """
        devices = []
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("maxInputChannels") > 0:
                devices.append(dev_info.get("name"))
        return devices

    def get_output_devices(self):
        """
        Returns a list of device names that have output channels.
        """
        devices = []
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("maxOutputChannels") > 0:
                devices.append(dev_info.get("name"))
        return devices

    def start_server(self):
        if self.is_server_running:
            return

        try:
            # Find indices from device names
            self.input_device_index = self.find_device_index_by_name(
                self.input_device_var.get(), input=True
            )
            self.output_device_index = self.find_device_index_by_name(
                self.output_device_var.get(), input=False
            )

            port = int(self.port_var.get())

            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("0.0.0.0", port))
            self.server_socket.listen(1)
            self.is_server_running = True

            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")

            threading.Thread(target=self.accept_client, daemon=True).start()

        except Exception as e:
            print("Error starting server:", e)

    def accept_client(self):
        print("Server listening for a connection...")
        try:
            self.client_socket, addr = self.server_socket.accept()
            print(f"Client connected from: {addr}")
            self.is_streaming = True

            # Create PyAudio streams
            self.stream_in = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=self.input_device_index
            )

            self.stream_out = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK,
                output_device_index=self.output_device_index
            )

            # Start threads to send/receive audio
            threading.Thread(target=self.send_audio, daemon=True).start()
            threading.Thread(target=self.receive_audio, daemon=True).start()

        except Exception as e:
            print("Error accepting client:", e)
            self.stop_server()

    def send_audio(self):
        while self.is_streaming:
            try:
                data = self.stream_in.read(CHUNK, exception_on_overflow=False)
                if self.client_socket:
                    self.client_socket.sendall(data)
            except:
                break
        print("Stopped sending audio.")

    def receive_audio(self):
        while self.is_streaming:
            try:
                data = self.client_socket.recv(CHUNK*2)  
                if not data:
                    break
                self.stream_out.write(data)
            except:
                break
        print("Stopped receiving audio.")
        self.stop_server()

    def stop_server(self):
        self.is_streaming = False
        self.is_server_running = False

        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()
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

        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def find_device_index_by_name(self, name, input=False):
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("name") == name:
                # Check if the device has input or output
                if input and dev_info.get("maxInputChannels") > 0:
                    return i
                elif not input and dev_info.get("maxOutputChannels") > 0:
                    return i
        return None

    def on_closing(self):
        self.stop_server()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = VoiceServer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
