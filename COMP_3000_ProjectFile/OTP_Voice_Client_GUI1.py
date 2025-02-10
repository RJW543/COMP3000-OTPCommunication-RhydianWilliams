#!/usr/bin/env python3
"""

A GUI client for real-time OTP-encrypted voice calls using Ngrok.
GUI Structure:
  - Ngrok Host and Port input with "Set Server Address"
  - User ID and Recipient ID input with "Connect to Server"
  - "Call" and "Hang Up" buttons for voice call control

Assumes an OTP file (otp_cipher.txt) where each page is 5000 characters
and the first 8 characters of each page are a sync header (skipped).
"""
import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import pyaudio

# Audio parameters
CHUNK_FRAMES = 1024
SAMPLE_WIDTH = 2           # 16-bit audio (2 bytes per frame)
CHUNK_SIZE = CHUNK_FRAMES * SAMPLE_WIDTH  # 2048 bytes per audio chunk
RATE = 16000

# OTP Reader for binary encryption/decryption
class OTPReader:
    def __init__(self, filename, page_size=5000, header_size=8, initial_offset=0):
        self.page_size = page_size
        self.header_size = header_size
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        otp_string = ''.join(lines)
        if len(otp_string) % page_size != 0:
            print("Warning: OTP file length is not an exact multiple of page size!")
        self.data = otp_string.encode('ascii')
        self.current_index = initial_offset

    def read(self, n):
        result = bytearray()
        while len(result) < n:
            page_start = (self.current_index // self.page_size) * self.page_size
            if self.current_index < page_start + self.header_size:
                self.current_index = page_start + self.header_size
            page_end = page_start + self.page_size
            bytes_left = page_end - self.current_index
            to_read = min(n - len(result), bytes_left)
            if self.current_index + to_read > len(self.data):
                raise Exception("Not enough OTP data! Pad exhausted.")
            result.extend(self.data[self.current_index:self.current_index + to_read])
            self.current_index += to_read
        return bytes(result)

class VoiceClientGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OTP Voice Client")
        self.geometry("400x400")
        self.resizable(False, False)

        # Variables for server address
        self.ngrok_host_var = tk.StringVar(value="0.tcp.ngrok.io")
        self.ngrok_port_var = tk.StringVar(value="65432")
        self.server_host = None
        self.server_port = None

        # Variables for connection info
        self.user_id_var = tk.StringVar()
        self.recipient_id_var = tk.StringVar()

        # OTP file 
        self.otp_file = "otp_cipher.txt"

        self.client_socket = None
        self.running = False
        self.send_thread = None
        self.recv_thread = None

        self.create_widgets()

    def create_widgets(self):
        # Frame for Ngrok address input
        frame1 = ttk.Frame(self)
        frame1.pack(padx=10, pady=5, fill="x")
        ttk.Label(frame1, text="Ngrok Host:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame1, textvariable=self.ngrok_host_var, width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(frame1, text="Ngrok Port:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame1, textvariable=self.ngrok_port_var, width=10).grid(row=1, column=1, sticky="w")
        ttk.Button(frame1, text="Set Server Address", command=self.set_server_address).grid(row=2, column=0, columnspan=2, pady=5)

        # Frame for connection information
        frame2 = ttk.Frame(self)
        frame2.pack(padx=10, pady=5, fill="x")
        ttk.Label(frame2, text="Your User ID:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame2, textvariable=self.user_id_var, width=20).grid(row=0, column=1, sticky="w")
        ttk.Label(frame2, text="Recipient ID:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame2, textvariable=self.recipient_id_var, width=20).grid(row=1, column=1, sticky="w")
        ttk.Button(frame2, text="Connect to Server", command=self.connect_to_server).grid(row=2, column=0, columnspan=2, pady=5)

        # Frame for call controls
        frame3 = ttk.Frame(self)
        frame3.pack(padx=10, pady=5, fill="x")
        self.call_button = ttk.Button(frame3, text="Call", command=self.start_call, state="disabled")
        self.call_button.grid(row=0, column=0, padx=5)
        self.hangup_button = ttk.Button(frame3, text="Hang Up", command=self.end_call, state="disabled")
        self.hangup_button.grid(row=0, column=1, padx=5)

        self.status_label = ttk.Label(self, text="Status: Not connected", relief="sunken", anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=10)

    def set_server_address(self):
        host = self.ngrok_host_var.get().strip()
        port_str = self.ngrok_port_var.get().strip()
        if not host or not port_str:
            messagebox.showerror("Error", "Please enter both Ngrok Host and Port.")
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Error", "Port must be a number.")
            return
        self.server_host = host
        self.server_port = port
        self.status_label.config(text=f"Server set to {self.server_host}:{self.server_port}")
        # Disable changes to Ngrok fields after setting the address
        self.ngrok_host_var.set(host)
        self.ngrok_port_var.set(str(port))

    def connect_to_server(self):
        if self.server_host is None or self.server_port is None:
            messagebox.showerror("Error", "Set the server address first.")
            return
        user_id = self.user_id_var.get().strip()
        recipient_id = self.recipient_id_var.get().strip()
        if not user_id or not recipient_id:
            messagebox.showerror("Error", "Enter both your User ID and Recipient ID.")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.server_host, self.server_port))
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            return

        # Send login message in the format: "user_id|recipient_id\n"
        login_msg = f"{user_id}|{recipient_id}\n"
        try:
            self.client_socket.sendall(login_msg.encode("utf-8"))
            response = self.client_socket.recv(1024).decode("utf-8").strip()
            if response != "Connected.":
                messagebox.showerror("Error", f"Server response: {response}")
                self.client_socket.close()
                return
        except Exception as e:
            messagebox.showerror("Error", f"Failed during login: {e}")
            self.client_socket.close()
            return

        messagebox.showinfo("Info", "Connected to server.")
        self.status_label.config(text="Connected. Ready to call.")
        self.call_button.config(state="normal")

    def start_call(self):
        if not self.client_socket:
            messagebox.showerror("Error", "Not connected to server.")
            return
        self.running = True
        self.call_button.config(state="disabled")
        self.hangup_button.config(state="normal")
        self.status_label.config(text="Call in progress...")

        # Set up OTP readers.
        self.send_otp = OTPReader(self.otp_file, initial_offset=0)
        self.recv_otp = OTPReader(self.otp_file, initial_offset=5000)
        self.send_thread = threading.Thread(target=self.send_audio, daemon=True)
        self.recv_thread = threading.Thread(target=self.receive_audio, daemon=True)
        self.send_thread.start()
        self.recv_thread.start()

    def end_call(self):
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except Exception:
                pass
        self.call_button.config(state="normal")
        self.hangup_button.config(state="disabled")
        self.status_label.config(text="Call ended.")

    def send_audio(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                        input=True, frames_per_buffer=CHUNK_FRAMES)
        try:
            while self.running:
                audio_data = stream.read(CHUNK_FRAMES, exception_on_overflow=False)
                otp_bytes = self.send_otp.read(len(audio_data))
                encrypted_chunk = bytes(a ^ b for a, b in zip(audio_data, otp_bytes))
                self.client_socket.sendall(encrypted_chunk)
        except Exception as e:
            print("Send audio error:", e)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def receive_audio(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=RATE,
                        output=True, frames_per_buffer=CHUNK_FRAMES)
        try:
            while self.running:
                data = self.recv_all(CHUNK_SIZE)
                if data is None:
                    break
                otp_bytes = self.recv_otp.read(len(data))
                decrypted_chunk = bytes(a ^ b for a, b in zip(data, otp_bytes))
                stream.write(decrypted_chunk)
        except Exception as e:
            print("Receive audio error:", e)
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

    def recv_all(self, n):
        data = b""
        while len(data) < n and self.running:
            try:
                packet = self.client_socket.recv(n - len(data))
                if not packet:
                    return None
                data += packet
            except Exception:
                return None
        return data

if __name__ == "__main__":
    app = VoiceClientGUI()
    app.mainloop()
