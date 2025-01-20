import tkinter as tk
from tkinter import messagebox
import socket
import threading
import pyaudio

class VoIPClientGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("Ngrok TCP VoIP Client")

        # Server info
        self.server_host = None
        self.server_port = None

        # User info
        self.user_id = None
        self.sock = None
        self.connected = False

        # Audio
        self.audio = pyaudio.PyAudio()
        self.stream_in = None   # microphone capture
        self.stream_out = None  # speaker output
        self.streaming = False

        self.build_gui()

    def build_gui(self):
        # Frame: Ngrok Host/Port
        ngrok_frame = tk.Frame(self.master)
        ngrok_frame.pack(pady=5)

        tk.Label(ngrok_frame, text="Ngrok Host:").pack(side=tk.LEFT, padx=5)
        self.host_entry = tk.Entry(ngrok_frame, width=18)
        self.host_entry.pack(side=tk.LEFT, padx=5)
        self.host_entry.insert(0, "0.tcp.ngrok.io")  # common placeholder

        tk.Label(ngrok_frame, text="Ngrok Port:").pack(side=tk.LEFT, padx=5)
        self.port_entry = tk.Entry(ngrok_frame, width=6)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        self.port_entry.insert(0, "12345")  # example

        set_server_btn = tk.Button(ngrok_frame, text="Set Server", command=self.set_server)
        set_server_btn.pack(side=tk.LEFT, padx=5)

        # Frame: user ID & connect
        user_frame = tk.Frame(self.master)
        user_frame.pack(pady=5)

        tk.Label(user_frame, text="User ID:").pack(side=tk.LEFT, padx=5)
        self.user_id_entry = tk.Entry(user_frame, width=10)
        self.user_id_entry.pack(side=tk.LEFT, padx=5)

        self.connect_btn = tk.Button(user_frame, text="Connect", command=self.connect_server)
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # Frame: call
        call_frame = tk.Frame(self.master)
        call_frame.pack(pady=5)

        tk.Label(call_frame, text="Call Recipient:").pack(side=tk.LEFT, padx=5)
        self.recipient_entry = tk.Entry(call_frame, width=10)
        self.recipient_entry.pack(side=tk.LEFT, padx=5)

        self.call_btn = tk.Button(call_frame, text="Start Call", command=self.start_call)
        self.call_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(call_frame, text="Stop Call", command=self.stop_call)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Frame: push-to-talk
        ptt_frame = tk.Frame(self.master)
        ptt_frame.pack(pady=5)

        self.ptt_btn = tk.Button(ptt_frame, text="Push to Talk", command=self.toggle_streaming, state=tk.DISABLED)
        self.ptt_btn.pack(side=tk.LEFT, padx=5)

    def set_server(self):
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        if not host or not port_str or not port_str.isdigit():
            messagebox.showerror("Error", "Invalid host or port.")
            return
        self.server_host = host
        self.server_port = int(port_str)
        messagebox.showinfo("Info", f"Server set to {self.server_host}:{self.server_port}.")

    def connect_server(self):
        if not self.server_host or not self.server_port:
            messagebox.showerror("Error", "Please set the server address (ngrok) first.")
            return

        user_id = self.user_id_entry.get().strip()
        if not user_id:
            messagebox.showerror("Error", "Please enter a valid user ID.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_host, self.server_port))
            self.sock.sendall(user_id.encode('utf-8'))

            response = self.sock.recv(1024).decode('utf-8')
            if response.startswith("ERROR"):
                messagebox.showerror("Error", response)
                self.sock.close()
                self.sock = None
                return
            elif response.startswith("OK"):
                self.user_id = user_id
                self.connected = True
                messagebox.showinfo("Info", f"Connected as {self.user_id}.")
                # Start receiving data (including audio)
                threading.Thread(target=self.receive_data, daemon=True).start()
                # Enable push-to-talk button now that we are connected
                self.ptt_btn.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")

    def start_call(self):
        if not self.connected:
            messagebox.showerror("Error", "Not connected to the server.")
            return
        recipient_id = self.recipient_entry.get().strip()
        if not recipient_id:
            messagebox.showerror("Error", "Enter a recipient ID.")
            return
        try:
            cmd = f"CALL|{recipient_id}".encode('utf-8')
            self.sock.sendall(cmd)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send CALL command: {e}")

    def stop_call(self):
        # In this simple example, we'll just do an empty CALL to clear it server side:
        try:
            self.sock.sendall(b"CALL|")
        except Exception as e:
            print(f"Error sending empty CALL command: {e}")

        # Also stop streaming if active
        if self.streaming:
            self.toggle_streaming()

        messagebox.showinfo("Info", "Call ended on client side.")

    def toggle_streaming(self):
        if not self.streaming:
            # Start mic capture
            self.start_mic_stream()
            self.streaming = True
            self.ptt_btn.config(text="Stop Talking")
        else:
            # Stop mic capture
            self.stop_mic_stream()
            self.streaming = False
            self.ptt_btn.config(text="Push to Talk")

    def start_mic_stream(self):
        if not self.stream_in:
            self.stream_in = self.audio.open(format=pyaudio.paInt16,
                                             channels=1,
                                             rate=16000,
                                             input=True,
                                             frames_per_buffer=1024)
        # Thread for sending mic data
        self.send_audio_thread = threading.Thread(target=self.send_audio_loop, daemon=True)
        self.send_audio_thread.start()

    def stop_mic_stream(self):
        if self.stream_in:
            self.stream_in.stop_stream()
            self.stream_in.close()
            self.stream_in = None

    def send_audio_loop(self):
        try:
            while self.streaming and self.connected and self.stream_in:
                data = self.stream_in.read(1024, exception_on_overflow=False)
                packet = b"AUDIO|" + data
                self.sock.sendall(packet)
        except Exception as e:
            print(f"Error sending audio: {e}")

    def receive_data(self):
        try:
            while self.connected:
                data = self.sock.recv(4096)
                if not data:
                    break

                # Parse "COMMAND|PAYLOAD"
                try:
                    header, payload = data.split(b'|', 1)
                    command = header.decode('utf-8')
                except ValueError:
                    continue

                if command == "AUDIO":
                    self.play_audio(payload)
                else:
                    # Could be INFO|..., ERROR|..., etc.
                    text = payload.decode('utf-8', errors='replace')
                    print(f"[Server {command}] {text}")
        except Exception as e:
            print(f"Error receiving data: {e}")
        finally:
            self.disconnect()

    def play_audio(self, data):
        if not self.stream_out:
            self.stream_out = self.audio.open(format=pyaudio.paInt16,
                                              channels=1,
                                              rate=16000,
                                              output=True)
        self.stream_out.write(data)

    def disconnect(self):
        if self.connected:
            self.connected = False
            if self.sock:
                self.sock.close()
                self.sock = None
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
