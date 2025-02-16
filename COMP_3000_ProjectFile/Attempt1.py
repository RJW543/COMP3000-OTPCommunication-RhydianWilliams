import socket
import threading
import pyaudio
import tkinter as tk
from tkinter import ttk

# Audio configuration
CHUNK = 1024             # Number of frames per buffer
FORMAT = pyaudio.paInt16 # 16-bit resolution
CHANNELS = 1             # Mono audio
RATE = 44100             # 44.1kHz sample rate
BUFFER_SIZE = 4096       # Socket buffer size for receiving audio

# Default host/port
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 50007

class VoiceCallApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Python Voice Call")

        # PyAudio instance
        self.audio = pyaudio.PyAudio()

        # Lists of devices
        self.input_devices = self.get_input_devices()
        self.output_devices = self.get_output_devices()

        # Selected device indexes
        self.selected_input_device_var = tk.StringVar()
        self.selected_output_device_var = tk.StringVar()

        # If we have devices, initialize the selected device to the first one
        if self.input_devices:
            self.selected_input_device_var.set(self.input_devices[0][1])  
        if self.output_devices:
            self.selected_output_device_var.set(self.output_devices[0][1])  

        # Streams
        self.stream_out = None
        self.stream_in = None

        # Networking
        self.server_socket = None
        self.client_socket = None
        self.listening_thread = None
        self.sending_thread = None
        self.running = False

        # Build GUI
        self.create_widgets()

    def get_input_devices(self):
        """
        Return a list of (device_index, device_name) for all valid input devices.
        """
        input_devs = []
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            # If maxInputChannels > 0, it's an input-capable device
            if dev_info.get('maxInputChannels', 0) > 0:
                name = dev_info.get('name', f"Device {i}")
                input_devs.append((i, name))
        return input_devs

    def get_output_devices(self):
        """
        Return a list of (device_index, device_name) for all valid output devices.
        """
        output_devs = []
        count = self.audio.get_device_count()
        for i in range(count):
            dev_info = self.audio.get_device_info_by_index(i)
            # If maxOutputChannels > 0, it's an output-capable device
            if dev_info.get('maxOutputChannels', 0) > 0:
                name = dev_info.get('name', f"Device {i}")
                output_devs.append((i, name))
        return output_devs

    def create_widgets(self):
        # Status label
        self.status_label = tk.Label(self.master, text="Not connected", fg="red")
        self.status_label.pack(pady=5)

        # Frame for device selection
        device_frame = tk.Frame(self.master)
        device_frame.pack(pady=5)

        # Input device selection
        tk.Label(device_frame, text="Microphone:").grid(row=0, column=0, padx=5, pady=2, sticky="e")
        input_device_names = [d[1] for d in self.input_devices]  # just the names
        self.input_device_menu = ttk.OptionMenu(
            device_frame,
            self.selected_input_device_var,
            self.selected_input_device_var.get(),
            *input_device_names
        )
        self.input_device_menu.grid(row=0, column=1, padx=5, pady=2)

        # Output device selection
        tk.Label(device_frame, text="Speakers/Headset:").grid(row=1, column=0, padx=5, pady=2, sticky="e")
        output_device_names = [d[1] for d in self.output_devices]
        self.output_device_menu = ttk.OptionMenu(
            device_frame,
            self.selected_output_device_var,
            self.selected_output_device_var.get(),
            *output_device_names
        )
        self.output_device_menu.grid(row=1, column=1, padx=5, pady=2)

        # Host button
        self.host_button = tk.Button(self.master, text="Host a Call", command=self.host_call)
        self.host_button.pack(pady=5)

        # Address entry
        self.address_label = tk.Label(self.master, text="Remote Address (host:port):")
        self.address_label.pack()

        self.address_entry = tk.Entry(self.master, width=25)
        self.address_entry.pack(pady=5)

        # Join call button
        self.call_button = tk.Button(self.master, text="Join a Call", command=self.join_call)
        self.call_button.pack(pady=5)

        # End call button
        self.end_call_button = tk.Button(self.master, text="End Call", command=self.end_call, state=tk.DISABLED)
        self.end_call_button.pack(pady=5)

    def host_call(self):
        """Start listening for an incoming connection on DEFAULT_HOST:DEFAULT_PORT."""
        if self.running:
            self.status_label.config(text="Already in a call.", fg="blue")
            return

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind((DEFAULT_HOST, DEFAULT_PORT))
            self.server_socket.listen(1)

            self.status_label.config(text=f"Hosting on {DEFAULT_HOST}:{DEFAULT_PORT}... waiting for connection.", fg="orange")

            # Accept the connection in a separate thread
            threading.Thread(target=self.accept_connection, daemon=True).start()
        except Exception as e:
            self.status_label.config(text=f"Error hosting: {e}", fg="red")

    def accept_connection(self):
        """Accepts an incoming connection and starts the audio."""
        try:
            self.client_socket, addr = self.server_socket.accept()
            self.server_socket.close()
            self.server_socket = None
            self.status_label.config(text=f"Connected to {addr}", fg="green")
            self.call_setup()
        except Exception as e:
            self.status_label.config(text=f"Accept error: {e}", fg="red")

    def join_call(self):
        """Connect to a remote host specified in the entry box (host:port)."""
        if self.running:
            self.status_label.config(text="Already in a call.", fg="blue")
            return

        address = self.address_entry.get().strip()
        if not address:
            self.status_label.config(text="Please enter a remote address.", fg="red")
            return

        try:
            host, port = address.split(":")
            port = int(port)
        except ValueError:
            self.status_label.config(text="Invalid address format. Use host:port.", fg="red")
            return

        # Connect
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((host, port))
            self.status_label.config(text=f"Connected to {host}:{port}", fg="green")
            self.call_setup()
        except Exception as e:
            self.status_label.config(text=f"Connection error: {e}", fg="red")

    def call_setup(self):
        """Once connected via self.client_socket, start audio streams and threads."""
        self.running = True
        self.end_call_button.config(state=tk.NORMAL)
        self.host_button.config(state=tk.DISABLED)
        self.call_button.config(state=tk.DISABLED)

        # Determine the actual device indexes from the user selection
        input_dev_index = None
        output_dev_index = None

        selected_input_name = self.selected_input_device_var.get()
        selected_output_name = self.selected_output_device_var.get()

        # Map from name -> index
        for idx, name in self.input_devices:
            if name == selected_input_name:
                input_dev_index = idx
                break

        for idx, name in self.output_devices:
            if name == selected_output_name:
                output_dev_index = idx
                break

        # Start audio input stream
        self.stream_in = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            input=True,
            frames_per_buffer=CHUNK,
            input_device_index=input_dev_index
        )

        # Start audio output stream
        self.stream_out = self.audio.open(
            format=FORMAT,
            channels=CHANNELS,
            rate=RATE,
            output=True,
            frames_per_buffer=CHUNK,
            output_device_index=output_dev_index
        )

        # Start receiving and sending audio in separate threads
        self.listening_thread = threading.Thread(target=self.receive_audio, daemon=True)
        self.sending_thread = threading.Thread(target=self.send_audio, daemon=True)
        self.listening_thread.start()
        self.sending_thread.start()

    def receive_audio(self):
        """Continuously receive audio data from the connected socket and play it."""
        while self.running:
            try:
                data = self.client_socket.recv(BUFFER_SIZE)
                if not data:
                    # Connection closed
                    break
                self.stream_out.write(data)
            except:
                break
        self.status_label.config(text="Disconnected", fg="red")
        self.cleanup_sockets()

    def send_audio(self):
        """Continuously capture audio from microphone and send it to the connected socket."""
        while self.running:
            try:
                data = self.stream_in.read(CHUNK)
                self.client_socket.sendall(data)
            except:
                break

    def end_call(self):
        """End the ongoing call and clean up."""
        self.running = False
        self.status_label.config(text="Call ended", fg="red")

        self.end_call_button.config(state=tk.DISABLED)
        self.host_button.config(state=tk.NORMAL)
        self.call_button.config(state=tk.NORMAL)

        self.cleanup_sockets()

        # Stop audio streams
        if self.stream_in is not None:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

        if self.stream_out is not None:
            self.stream_out.stop_stream()
            self.stream_out.close()
            self.stream_out = None

    def cleanup_sockets(self):
        """Close the open sockets."""
        try:
            if self.client_socket:
                self.client_socket.close()
        except:
            pass
        self.client_socket = None

        try:
            if self.server_socket:
                self.server_socket.close()
        except:
            pass
        self.server_socket = None

def main():
    root = tk.Tk()
    app = VoiceCallApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
