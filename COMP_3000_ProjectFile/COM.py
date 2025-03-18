import tkinter as tk
from tkinter import ttk
import pyaudio
import socket
import threading
import subprocess
import re
import time
import sys

class VoiceChatApp:
    def __init__(self, master):
        self.master = master
        self.master.title("loclx + UDP Voice Chat")

        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100

        self.is_running = False
        self.loclx_process = None  
        self.sock = None
        self.send_thread = None
        self.recv_thread = None
        self.input_stream = None
        self.output_stream = None

        self.p = pyaudio.PyAudio()


        row = 0
        ttk.Label(master, text="Local Port to Expose (UDP):").grid(row=row, column=0, pady=5, padx=5, sticky='e')
        self.local_port_var = tk.StringVar(value="5001")
        ttk.Entry(master, textvariable=self.local_port_var).grid(row=row, column=1, pady=5, padx=5, sticky='w')
        row += 1

        ttk.Label(master, text="loclx Forwarding Info:").grid(row=row, column=0, pady=5, padx=5, sticky='e')
        self.forwarding_info_var = tk.StringVar(value="—")
        self.forwarding_info_label = ttk.Label(master, textvariable=self.forwarding_info_var)
        self.forwarding_info_label.grid(row=row, column=1, pady=5, padx=5, sticky='w')
        row += 1

        ttk.Label(master, text="Remote Host/IP:").grid(row=row, column=0, pady=5, padx=5, sticky='e')
        self.remote_host_var = tk.StringVar(value="127.0.0.1")
        self.remote_host_entry = ttk.Entry(master, textvariable=self.remote_host_var)
        self.remote_host_entry.grid(row=row, column=1, pady=5, padx=5, sticky='w')
        row += 1

        ttk.Label(master, text="Remote Port:").grid(row=row, column=0, pady=5, padx=5, sticky='e')
        self.remote_port_var = tk.StringVar(value="5001")
        self.remote_port_entry = ttk.Entry(master, textvariable=self.remote_port_var)
        self.remote_port_entry.grid(row=row, column=1, pady=5, padx=5, sticky='w')
        row += 1

        ttk.Label(master, text="Audio Input Device:").grid(row=row, column=0, pady=5, padx=5, sticky='e')
        self.input_device_list = self.get_input_devices()
        self.input_device_var = tk.StringVar(value=self.input_device_list[0] if self.input_device_list else "Default")
        self.input_device_menu = ttk.OptionMenu(master, self.input_device_var,
                                                self.input_device_var.get(),
                                                *self.input_device_list)
        self.input_device_menu.grid(row=row, column=1, pady=5, padx=5, sticky='w')
        row += 1

        self.start_button = ttk.Button(master, text="Start", command=self.start_tunnel_and_chat)
        self.start_button.grid(row=row, column=0, pady=5, padx=5, sticky='ew')

        self.stop_button = ttk.Button(master, text="Stop", command=self.stop_chat, state=tk.DISABLED)
        self.stop_button.grid(row=row, column=1, pady=5, padx=5, sticky='ew')

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def get_input_devices(self):
        """Return a list of input device names from PyAudio."""
        devices = []
        count = self.p.get_device_count()
        for i in range(count):
            info = self.p.get_device_info_by_index(i)
            if info.get('maxInputChannels', 0) > 0:
                devices.append(info['name'])
        return devices

    def start_tunnel_and_chat(self):
        """Single entry point: 
           1. Start loclx 
           2. Parse the domain info 
           3. Start sending/receiving audio.
        """
        if self.is_running:
            return

        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.DISABLED)

        local_port = self.local_port_var.get().strip()
        self.loclx_thread = threading.Thread(target=self.run_loclx, args=(local_port,))
        self.loclx_thread.daemon = True
        self.loclx_thread.start()

    def run_loclx(self, local_port):
        """
        Runs loclx in a background process, parses its output 
        to find the forwarding info, and updates the GUI.
        """
        try:
            cmd = ["loclx", "tunnel", "udp", "--port", local_port]

            self.loclx_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True
            )

            for line in self.loclx_process.stdout:
                print("loclx:", line.strip())
                if "Forwarding from " in line:
                    match = re.search(r"Forwarding from udp://([^:]+):(\d+)", line)
                    if match:
                        domain = match.group(1)
                        fwd_port = match.group(2)

                        self.forwarding_info_var.set(f"{domain}:{fwd_port}")

                        self.master.after(0, self.start_streaming)

        except Exception as e:
            print(f"Error running loclx: {e}")
            self.master.after(0, self.reset_buttons)
        
    def start_streaming(self):
        """Actually start the UDP socket, send/receive threads, and audio streams."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_port = int(self.local_port_var.get())
            self.sock.bind(('', local_port))

            input_device_index = self.get_device_index_by_name(self.input_device_var.get())
            self.input_stream = self.p.open(format=self.FORMAT,
                                            channels=self.CHANNELS,
                                            rate=self.RATE,
                                            input=True,
                                            frames_per_buffer=self.CHUNK,
                                            input_device_index=input_device_index)
            self.output_stream = self.p.open(format=self.FORMAT,
                                             channels=self.CHANNELS,
                                             rate=self.RATE,
                                             output=True,
                                             frames_per_buffer=self.CHUNK)
            
            self.is_running = True
            remote_host = self.remote_host_var.get().strip()
            remote_port = int(self.remote_port_var.get().strip())

            self.send_thread = threading.Thread(target=self.send_audio, args=(remote_host, remote_port))
            self.recv_thread = threading.Thread(target=self.receive_audio)

            self.send_thread.start()
            self.recv_thread.start()

            self.stop_button.configure(state=tk.NORMAL)
            print("Audio streaming started.")
        except Exception as e:
            print(f"Error starting streaming: {e}")
            self.reset_buttons()

    def send_audio(self, remote_host, remote_port):
        """Capture audio from mic and send via UDP."""
        while self.is_running:
            try:
                data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                self.sock.sendto(data, (remote_host, remote_port))
            except Exception as e:
                print(f"Send audio error: {e}")
                break

    def receive_audio(self):
        """Receive audio via UDP and play it."""
        while self.is_running:
            try:
                data, _ = self.sock.recvfrom(self.CHUNK * 2)  
                self.output_stream.write(data)
            except Exception as e:
                print(f"Receive audio error: {e}")
                break

    def stop_chat(self):
        """Stop everything: threads, streams, loclx."""
        self.is_running = False

        if self.send_thread and self.send_thread.is_alive():
            self.send_thread.join(timeout=1)
        if self.recv_thread and self.recv_thread.is_alive():
            self.recv_thread.join(timeout=1)

        if self.sock:
            self.sock.close()
            self.sock = None

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

        if self.loclx_process and self.loclx_process.poll() is None:
            self.loclx_process.terminate()
            self.loclx_process = None

        self.reset_buttons()
        print("Chat stopped.")

    def reset_buttons(self):
        """Reset button states after stopping or error."""
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)

    def get_device_index_by_name(self, device_name):
        """Get the pyaudio device index for a given device name."""
        count = self.p.get_device_count()
        for i in range(count):
            info = self.p.get_device_info_by_index(i)
            if info['name'] == device_name:
                return i
        return None

    def on_closing(self):
        """Gracefully stop everything on window close."""
        if self.is_running:
            self.stop_chat()
        self.p.terminate()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = VoiceChatApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
