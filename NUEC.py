import tkinter as tk
import pyaudio
import socket
import threading

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

class VoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Voice Client")

        self.client_socket = None
        self.audio = pyaudio.PyAudio()

        self.input_device_index = None
        self.output_device_index = None
        self.stream_in = None
        self.stream_out = None

        self.is_connected = False
        self.is_streaming = False

        self.input_device_var = tk.StringVar()
        self.output_device_var = tk.StringVar()
        self.server_ip_var = tk.StringVar(value="127.0.0.1")
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

        # Server IP and Port
        tk.Label(self.master, text="Server IP:").grid(row=2, column=0, padx=5, pady=5)
        tk.Entry(self.master, textvariable=self.server_ip_var).grid(row=2, column=1, padx=5, pady=5)

        tk.Label(self.master, text="Port:").grid(row=3, column=0, padx=5, pady=5)
        tk.Entry(self.master, textvariable=self.port_var).grid(row=3, column=1, padx=5, pady=5)

        # Connect and Disconnect buttons
        self.connect_button = tk.Button(self.master, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=4, column=0, padx=5, pady=5)

        self.disconnect_button = tk.Button(self.master, text="Disconnect", command=self.disconnect, state="disabled")
        self.disconnect_button.grid(row=4, column=1, padx=5, pady=5)

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

    def connect_to_server(self):
        if self.is_connected:
            return

        try:
            self.input_device_index = self.find_device_index_by_name(
                self.input_device_var.get(), input=True
            )
            self.output_device_index = self.find_device_index_by_name(
                self.output_device_var.get(), input=False
            )

            server_ip = self.server_ip_var.get()
            port = int(self.port_var.get())

            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((server_ip, port))
            self.is_connected = True
            self.is_streaming = True

            # Create audio streams
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

            # Start threads
            threading.Thread(target=self.send_audio, daemon=True).start()
            threading.Thread(target=self.receive_audio, daemon=True).start()

            self.connect_button.config(state="disabled")
            self.disconnect_button.config(state="normal")

        except Exception as e:
            print("Error connecting to server:", e)

    def send_audio(self):
        while self.is_streaming:
            try:
                data = self.stream_in.read(CHUNK, exception_on_overflow=False)
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
        self.disconnect()

    def disconnect(self):
        self.is_streaming = False
        self.is_connected = False

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

        self.connect_button.config(state="normal")
        self.disconnect_button.config(state="disabled")

    def find_device_index_by_name(self, name, input=False):
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("name") == name:
                if input and dev_info.get("maxInputChannels") > 0:
                    return i
                elif not input and dev_info.get("maxOutputChannels") > 0:
                    return i
        return None

    def on_closing(self):
        self.disconnect()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = VoiceClient(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
