#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk
import pyaudio
import socket
import threading

class VoiceClient:
    def __init__(self, master):
        self.master = master
        self.master.title("UDP Voice Client")

        # Audio config
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100

        self.is_running = False
        self.sock = None
        self.send_thread = None
        self.recv_thread = None
        self.input_stream = None
        self.output_stream = None

        self.p = pyaudio.PyAudio()


        row = 0

        ttk.Label(master, text="Server Host:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.server_host_var = tk.StringVar(value="myexample.loclx.io")
        ttk.Entry(master, textvariable=self.server_host_var).grid(row=row, column=1, padx=5, pady=5, sticky='w')
        row += 1

        ttk.Label(master, text="Server Port:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.server_port_var = tk.StringVar(value="12345")
        ttk.Entry(master, textvariable=self.server_port_var).grid(row=row, column=1, padx=5, pady=5, sticky='w')
        row += 1

        ttk.Label(master, text="Local Listen Port (for replies):").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.local_port_var = tk.StringVar(value="0")  # 0 => OS picks a free port
        ttk.Entry(master, textvariable=self.local_port_var).grid(row=row, column=1, padx=5, pady=5, sticky='w')
        row += 1

        # Audio input device
        ttk.Label(master, text="Audio Input Device:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.input_device_list = self.get_input_devices()
        default_input = self.input_device_list[0] if self.input_device_list else "Default"
        self.input_device_var = tk.StringVar(value=default_input)
        ttk.OptionMenu(
            master,
            self.input_device_var,
            default_input,
            *self.input_device_list
        ).grid(row=row, column=1, padx=5, pady=5, sticky='w')
        row += 1

        # Audio output device
        ttk.Label(master, text="Audio Output Device:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        self.output_device_list = self.get_output_devices()
        default_output = self.output_device_list[0] if self.output_device_list else "Default"
        self.output_device_var = tk.StringVar(value=default_output)
        ttk.OptionMenu(
            master,
            self.output_device_var,
            default_output,
            *self.output_device_list
        ).grid(row=row, column=1, padx=5, pady=5, sticky='w')
        row += 1

        # Start/Stop
        self.start_button = ttk.Button(master, text="Start", command=self.start_client)
        self.start_button.grid(row=row, column=0, padx=5, pady=5, sticky='ew')

        self.stop_button = ttk.Button(master, text="Stop", command=self.stop_client, state=tk.DISABLED)
        self.stop_button.grid(row=row, column=1, padx=5, pady=5, sticky='ew')

        # Cleanup
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)


    def get_input_devices(self):
        """Return a list of *input-capable* device names."""
        devices = []
        count = self.p.get_device_count()
        for i in range(count):
            info = self.p.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                devices.append(info['name'])
        return devices

    def get_output_devices(self):
        """Return a list of *output-capable* device names."""
        devices = []
        count = self.p.get_device_count()
        for i in range(count):
            info = self.p.get_device_info_by_index(i)
            if info.get('maxOutputChannels', 0) > 0:
                devices.append(info['name'])
        return devices

    def get_device_index_by_name(self, device_name, is_output=False):
        """
        Return PyAudio device index for the given device name,
        ensuring we check input vs output capability as needed.
        """
        count = self.p.get_device_count()
        for i in range(count):
            info = self.p.get_device_info_by_index(i)
            if info['name'] == device_name:
                if is_output and info.get('maxOutputChannels', 0) > 0:
                    return i
                if not is_output and info.get('maxInputChannels', 0) > 0:
                    return i
        return None  

    def start_client(self):
        if self.is_running:
            return

        server_host = self.server_host_var.get().strip()
        server_port = int(self.server_port_var.get().strip())
        local_port = int(self.local_port_var.get().strip())

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind(('', local_port))  
        except OSError as e:
            print(f"Error binding local port {local_port}: {e}")
            return

        input_device_index = self.get_device_index_by_name(self.input_device_var.get(), is_output=False)
        output_device_index = self.get_device_index_by_name(self.output_device_var.get(), is_output=True)

        try:
            self.input_stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                input_device_index=input_device_index
            )
            self.output_stream = self.p.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
                output_device_index=output_device_index
            )
        except Exception as e:
            print(f"Error opening audio streams: {e}")
            self.sock.close()
            self.sock = None
            return

        # Start threads
        self.is_running = True
        self.send_thread = threading.Thread(target=self.send_audio, args=(server_host, server_port))
        self.recv_thread = threading.Thread(target=self.receive_audio)
        self.send_thread.start()
        self.recv_thread.start()

        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)

    def send_audio(self, server_host, server_port):
        """Continuously read audio from mic and send to server."""
        while self.is_running:
            try:
                data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                self.sock.sendto(data, (server_host, server_port))
            except Exception as e:
                print(f"Send audio error: {e}")
                break

    def receive_audio(self):
        """Continuously receive audio from server and play it."""
        while self.is_running:
            try:
                data, addr = self.sock.recvfrom(self.CHUNK * 2)
                self.output_stream.write(data)
            except Exception as e:
                print(f"Receive audio error: {e}")
                break

    def stop_client(self):
        if not self.is_running:
            return

        self.is_running = False

        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=1)
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1)

        if self.sock:
            self.sock.close()
            self.sock = None

        # Close audio streams
        if self.input_stream:
            if not self.input_stream.is_stopped():
                self.input_stream.stop_stream()
            self.input_stream.close()
            self.input_stream = None

        if self.output_stream:
            if not self.output_stream.is_stopped():
                self.output_stream.stop_stream()
            self.output_stream.close()
            self.output_stream = None

        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        print("Client stopped.")

    def on_closing(self):
        if self.is_running:
            self.stop_client()
        self.p.terminate()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = VoiceClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()
