import tkinter as tk
from tkinter import messagebox
import socket
import threading
import pyaudio

class VoIPClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("TCP VoIP Client")

        # Server info
        self.server_host = None
        self.server_port = None

        # User info
        self.user_id = None
        self.socket = None
        self.connected = False

        # Audio Streams
        self.audio = pyaudio.PyAudio()
        self.stream_in = None   # For capturing microphone
        self.stream_out = None  # For playing received audio
        self.streaming = False

        self.build_gui()

    def build_gui(self):
        # Frame for server host/port
        server_frame = tk.Frame(self.master)
        server_frame.pack(pady=5)

        tk.Label(server_frame, text="Server Host:").pack(side=tk.LEFT, padx=5)
        self.host_entry = tk.Entry(server_frame, width=15)
        self.host_entry.pack(side=tk.LEFT, padx=5)
        self.host_entry.insert(0, "127.0.0.1")

        tk.Label(server_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_entry = tk.Entry(server_frame, width=6)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        self.port_entry.insert(0, "50000")

        self.set_server_btn = tk.Button(server_frame, text="Set Server", command=self.set_server)
        self.set_server_btn.pack(side=tk.LEFT, padx=5)

        # Frame for user ID
        user_frame = tk.Frame(self.master)
        user_frame.pack(pady=5)
        tk.Label(user_frame, text="User ID:").pack(side=tk.LEFT, padx=5)
        self.user_id_entry = tk.Entry(user_frame, width=10)
        self.user_id_entry.pack(side=tk.LEFT, padx=5)

        self.connect_btn = tk.Button(user_frame, text="Connect", command=self.connect_server)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # Frame for call management
        call_frame = tk.Frame(self.master)
        call_frame.pack(pady=5)

        tk.Label(call_frame, text="Call Recipient ID:").pack(side=tk.LEFT, padx=5)
        self.recipient_entry = tk.Entry(call_frame, width=10)
        self.recipient_entry.pack(side=tk.LEFT, padx=5)
        self.call_btn = tk.Button(call_frame, text="Start Call", command=self.start_call)
        self.call_btn.pack(side=tk.LEFT, padx=5)
        self.stop_call_btn = tk.Button(call_frame, text="Stop Call", command=self.stop_call)
        self.stop_call_btn.pack(side=tk.LEFT, padx=5)

        # Frame for push-to-talk
        ptt_frame = tk.Frame(self.master)
        ptt_frame.pack(pady=5)
        self.ptt_btn = tk.Button(ptt_frame, text="Push to Talk", command=self.toggle_streaming, state=tk.DISABLED)
        self.ptt_btn.pack(side=tk.LEFT, padx=5)

    def set_server(self):
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()

        if not host or not port_str.isdigit():
            messagebox.showerror("Error", "Invalid host or port.")
            return

        self.server_host = host
        self.server_port = int(port_str)
        messagebox.showinfo("Info", f"Server set to {self.server_host}:{self.server_port}.")

        # Disable these entries
        self.host_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)
        self.set_server_btn.config(state=tk.DISABLED)

    def connect_server(self):
        if not self.server_host or not self.server_port:
            messagebox.showerror("Error", "Please set the server address first.")
            return

        user_id = self.user_id_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "Please enter a valid user ID.")
            return

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_host, self.server_port))
            # Send user ID
            self.socket.sendall(user_id.encode('utf-8'))
            response = self.socket.recv(1024).decode('utf-8')
            if response.startswith("ERROR"):
                messagebox.showerror("Error", response)
                self.socket.close()
                self.socket = None
                return
            elif response.startswith("OK"):
                self.user_id = user_id
                self.connected = True
                messagebox.showinfo("Info", f"Connected as {self.user_id}.")
                # Start a thread to receive audio
                threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")

    def start_call(self):
        """Send a command to the server indicating to call a recipient."""
        if not self.connected:
            messagebox.showerror("Error", "Not connected to the server.")
            return

        recipient_id = self.recipient_entry.get().strip()
        if not recipient_id:
            messagebox.showerror("Error", "Enter a recipient ID.")
            return

        try:
            cmd = f"CALL|{recipient_id}".encode('utf-8')
            self.socket.sendall(cmd)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send CALL command: {e}")

    def stop_call(self):
        """Stop sending audio. Reset any call target client-side."""
        # Not explicitly notifing the server to remove the call target in this simplified example.
        messagebox.showinfo("Info", "Call ended on client side.")
        # Turn off streaming if active
        if self.streaming:
            self.toggle_streaming()
        # Clear local call state by just sending a blank call target
        try:
            cmd = "CALL|".encode('utf-8')  # empty recipient
            self.socket.sendall(cmd)
        except Exception as e:
            print(f"Error sending empty CALL command: {e}")

    def toggle_streaming(self):
        """Push-to-talk toggle: start/stop capturing audio from mic and sending."""
        if not self.streaming:
            # Start capturing from mic
            self.start_mic_stream()
            self.streaming = True
            self.ptt_btn.config(text="Stop Talking")
        else:
            # Stop capturing
            self.stop_mic_stream()
            self.streaming = False
            self.ptt_btn.config(text="Push to Talk")

    def start_mic_stream(self):
        """Open PyAudio stream for microphone capture and start a thread to send audio data."""
        if self.stream_in is None:
            self.stream_in = self.audio.open(format=pyaudio.paInt16,
                                             channels=1,
                                             rate=16000,
                                             input=True,
                                             frames_per_buffer=1024)
        # Start sending in a background thread
        self.send_audio_thread = threading.Thread(target=self.send_audio_loop, daemon=True)
        self.send_audio_thread.start()

    def stop_mic_stream(self):
        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

    def send_audio_loop(self):
        """
        Continuously read audio frames from the microphone and send them to the server
        while streaming is True.
        """
        try:
            while self.streaming and self.connected and self.stream_in is not None:
                data = self.stream_in.read(1024, exception_on_overflow=False)
                packet = b"AUDIO|" + data
                self.socket.sendall(packet)
        except Exception as e:
            print(f"Error sending audio: {e}")

    def receive_data(self):
        """
        Continuously listen for data from the server.
        - If it's "AUDIO|<raw_bytes>", play it.
        - Else handle other server messages (INFO|..., ERROR|...).
        """
        try:
            while self.connected:
                data = self.socket.recv(4096)
                if not data:
                    break

                # Separate header from payload
                try:
                    header, payload = data.split(b'|', 1)
                    command = header.decode('utf-8')
                except ValueError:
                    continue

                if command == "AUDIO":
                    # Play this audio data
                    self.play_audio(payload)
                else:
                    # Could handle INFO|..., ERROR|..., etc.
                    text = payload.decode('utf-8')
                    print(f"[Server {command}] {text}")

        except Exception as e:
            print(f"Error receiving data: {e}")
        finally:
            self.disconnect()

    def play_audio(self, data):
        """Play raw audio data through an output stream."""
        # Lazy init stream_out
        if self.stream_out is None:
            self.stream_out = self.audio.open(format=pyaudio.paInt16,
                                              channels=1,
                                              rate=16000,
                                              output=True)

        self.stream_out.write(data)

    def disconnect(self):
        """Close resources and mark disconnected."""
        if self.connected:
            self.connected = False
            if self.socket:
                self.socket.close()
                self.socket = None
            if self.stream_in:
                self.stop_mic_stream()
            if self.stream_out:
                self.stream_out.stop_stream()
                self.stream_out.close()
                self.stream_out = None
            print("Disconnected from server.")

if __name__ == "__main__":
    root = tk.Tk()
    app = VoIPClientGUI(root)
    root.mainloop()
