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

        self.audio = pyaudio.PyAudio()
        self.stream_in = None
        self.stream_out = None

        self.client_socket = None
        self.is_connected = False
        self.is_streaming = False

        # GUI Variables
        self.input_device_var = tk.StringVar()
        self.output_device_var = tk.StringVar()
        self.server_address_var = tk.StringVar(value="your-subdomain.loca.lt:5000")

        self.create_widgets()

    def create_widgets(self):
        # Input device selection
        tk.Label(self.master, text="Input Device:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.OptionMenu(self.master, self.input_device_var, *self.get_input_devices()).grid(
            row=0, column=1, padx=5, pady=5, sticky="ew"
        )

        # Output device selection
        tk.Label(self.master, text="Output Device:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        tk.OptionMenu(self.master, self.output_device_var, *self.get_output_devices()).grid(
            row=1, column=1, padx=5, pady=5, sticky="ew"
        )

        # Server address
        tk.Label(self.master, text="Server Address:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(self.master, textvariable=self.server_address_var).grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # Connect/Disconnect
        self.connect_button = tk.Button(self.master, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=3, column=0, padx=5, pady=5)

        self.disconnect_button = tk.Button(self.master, text="Disconnect", command=self.disconnect, state="disabled")
        self.disconnect_button.grid(row=3, column=1, padx=5, pady=5)

    def get_input_devices(self):
        devices = []
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("maxInputChannels") > 0:
                devices.append(dev_info.get("name"))
        return devices

    def get_output_devices(self):
        devices = []
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("maxOutputChannels") > 0:
                devices.append(dev_info.get("name"))
        return devices

    def find_device_index_by_name(self, name, is_input=False):
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get("name") == name:
                if is_input and dev_info.get("maxInputChannels") > 0:
                    return i
                elif not is_input and dev_info.get("maxOutputChannels") > 0:
                    return i
        return None

    def connect_to_server(self):
        if self.is_connected:
            return

        # Parse input/output device indices
        input_idx = self.find_device_index_by_name(self.input_device_var.get(), is_input=True)
        output_idx = self.find_device_index_by_name(self.output_device_var.get(), is_input=False)

        address = self.server_address_var.get().strip()  
        if ":" not in address:
            print("Invalid address. Use domain:port")
            return

        host, port = address.split(":")
        port = int(port)

        try:
            # Connect
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.is_connected = True
            self.is_streaming = True

            # Open PyAudio streams
            self.stream_in = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK,
                input_device_index=input_idx
            )
            self.stream_out = self.audio.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                output=True,
                frames_per_buffer=CHUNK,
                output_device_index=output_idx
            )

            # Start threads for sending & receiving
            threading.Thread(target=self.send_audio, daemon=True).start()
            threading.Thread(target=self.receive_audio, daemon=True).start()

            # Update GUI
            self.connect_button.config(state="disabled")
            self.disconnect_button.config(state="normal")

        except Exception as e:
            print("Connection error:", e)

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
                data = self.client_socket.recv(CHUNK * 2)
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

        # Close streams
        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

        if self.stream_out:
            self.stream_out.stop_stream()
            self.stream_out.close()
            self.stream_out = None

        # Close socket
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None

        # Update GUI
        self.connect_button.config(state="normal")
        self.disconnect_button.config(state="disabled")

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
