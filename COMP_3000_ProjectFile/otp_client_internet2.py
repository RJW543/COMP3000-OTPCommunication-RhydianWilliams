import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
from pathlib import Path
import fcntl
import requests

# Initially no host/port set; we will fetch from the server
SERVER_HOST = None
SERVER_PORT = None

# --- OTP Related Functions ---

def load_otp_pages(file_name="otp_cipher.txt"):
    otp_pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        return otp_pages
    with file_path.open("r") as file:
        for line in file:
            identifier = line[:8]
            content = line[8:].strip()
            otp_pages.append((identifier, content))
    return otp_pages

def load_used_pages(file_name="used_pages.txt"):
    file_path = Path(file_name)
    if not file_path.exists():
        return set()
    with file_path.open("r") as file:
        return {line.strip() for line in file}

def save_used_page(identifier, file_name="used_pages.txt"):
    with open(file_name, "a") as file:
        file.write(f"{identifier}\n")

def get_next_otp_page_linux(otp_pages, used_identifiers, lock_file="used_pages.lock"):
    with open(lock_file, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for identifier, content in otp_pages:
            if identifier not in used_identifiers:
                save_used_page(identifier)
                used_identifiers.add(identifier)
                fcntl.flock(lock, fcntl.LOCK_UN)
                return identifier, content
        fcntl.flock(lock, fcntl.LOCK_UN)
    return None, None

def encrypt_message(message, otp_content):
    encrypted_message = []
    for i, char in enumerate(message):
        if i >= len(otp_content):
            break
        encrypted_char = chr(ord(char) ^ ord(otp_content[i]))
        encrypted_message.append(encrypted_char)
    return ''.join(encrypted_message)

def decrypt_message(encrypted_message, otp_content):
    decrypted_message = []
    for i, char in enumerate(encrypted_message):
        if i >= len(otp_content):
            break
        decrypted_char = chr(ord(char) ^ ord(otp_content[i]))
        decrypted_message.append(decrypted_char)
    return ''.join(decrypted_message)

# --- Client Class ---

class OTPClient:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Messaging Client")

        self.otp_pages = load_otp_pages()
        self.used_identifiers = load_used_pages()

        # Frame for host/port fetching
        self.address_frame = tk.Frame(master)
        self.address_frame.pack(padx=10, pady=10)

        self.server_ip_label = tk.Label(self.address_frame, text="Server IP (for ngrok info):")
        self.server_ip_label.pack(side=tk.LEFT)

        self.server_ip_entry = tk.Entry(self.address_frame, width=30)
        self.server_ip_entry.pack(side=tk.LEFT)
        self.server_ip_entry.insert(0, "127.0.0.1")  # or the actual server machine IP

        self.fetch_button = tk.Button(self.address_frame, text="Fetch Ngrok Address", command=self.fetch_ngrok_address)
        self.fetch_button.pack(side=tk.LEFT)

        # GUI setup for user ID
        self.user_id_frame = tk.Frame(master)
        self.user_id_label = tk.Label(self.user_id_frame, text="Enter your userID:")
        self.user_id_label.pack(side=tk.LEFT)

        self.user_id_entry = tk.Entry(self.user_id_frame, width=30)
        self.user_id_entry.pack(side=tk.LEFT)

        self.connect_button = tk.Button(self.user_id_frame, text="Connect", command=self.connect_to_server)
        self.connect_button.pack(side=tk.LEFT)

        # Message frame setup (hidden initially)
        self.message_frame = tk.Frame(master)
        self.user_id_display = tk.Label(self.message_frame, text="")
        self.user_id_display.pack(pady=5)

        self.chat_area = scrolledtext.ScrolledText(self.message_frame, height=15, width=50)
        self.chat_area.pack(pady=5)
        self.chat_area.config(state=tk.DISABLED)

        self.recipient_input = tk.Entry(self.message_frame, width=50)
        self.recipient_input.pack(pady=5)
        self.recipient_input.insert(0, "Enter recipient userID:")

        self.text_input = tk.Entry(self.message_frame, width=50)
        self.text_input.pack(pady=5)

        self.send_button = tk.Button(self.message_frame, text="Send", command=self.send_message)
        self.send_button.pack()

        self.client_socket = None

    def fetch_ngrok_address(self):
        server_ip = self.server_ip_entry.get().strip()
        if not server_ip:
            messagebox.showwarning("Warning", "Please enter the server IP.")
            return

        try:
            url = f"http://{server_ip}:5000/ngrok"
            response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                global SERVER_HOST, SERVER_PORT
                SERVER_HOST = data.get("host")
                SERVER_PORT = data.get("port")
                if SERVER_HOST and SERVER_PORT:
                    messagebox.showinfo("Info", f"Ngrok Address: {SERVER_HOST}:{SERVER_PORT}")
                    # Now show the user ID frame to connect
                    self.user_id_frame.pack(padx=10, pady=10)
                else:
                    messagebox.showerror("Error", "Failed to retrieve Ngrok address from the server.")
            else:
                messagebox.showerror("Error", f"Failed to fetch Ngrok address: HTTP {response.status_code}")
        except Exception as e:
            messagebox.showerror("Error", f"Error fetching Ngrok address: {e}")

    def connect_to_server(self):
        if SERVER_HOST is None or SERVER_PORT is None:
            messagebox.showwarning("Warning", "Please fetch the Ngrok address first.")
            return

        self.user_id = self.user_id_entry.get()
        if not self.user_id:
            messagebox.showwarning("Warning", "Please enter a userID.")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((SERVER_HOST, int(SERVER_PORT)))
            self.client_socket.send(self.user_id.encode("utf-8"))
            response = self.client_socket.recv(1024).decode("utf-8")
            if response == "UserID already taken. Connection closed.":
                messagebox.showerror("Error", response)
                self.client_socket.close()
                return
            messagebox.showinfo("Info", "Connected to the server.")
            self.user_id_frame.pack_forget()
            self.message_frame.pack(padx=10, pady=10)
            self.user_id_display.config(text=f"Your userID: {self.user_id}")

            # Start thread to listen for incoming messages
            receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
            receive_thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to the server: {e}")

    def get_next_available_otp(self):
        return get_next_otp_page_linux(self.otp_pages, self.used_identifiers)

    def send_message(self):
        recipient_id = self.recipient_input.get().strip().replace("Enter recipient userID:", "")
        message = self.text_input.get()
        if not recipient_id or recipient_id == "Enter recipient userID":
            messagebox.showwarning("Warning", "Please enter a valid recipient userID.")
            return
        if not message:
            messagebox.showwarning("Warning", "Please enter a message.")
            return
        if recipient_id == self.user_id:
            messagebox.showwarning("Warning", "You cannot send a message to yourself.")
            return

        otp_identifier, otp_content = self.get_next_available_otp()
        if otp_identifier and otp_content:
            encrypted_message = encrypt_message(message, otp_content)
            full_message = f"{recipient_id}|{otp_identifier}:{encrypted_message}"
            if self.client_socket:
                self.client_socket.send(full_message.encode("utf-8"))
                self.text_input.delete(0, tk.END)
                self.update_chat_area(f"Me (Encrypted to {recipient_id}): {encrypted_message}")

    def receive_messages(self):
        while True:
            try:
                if self.client_socket:
                    message = self.client_socket.recv(1024).decode("utf-8")
                    if message:
                        sender_id, data = message.split("|", 1)
                        otp_identifier, actual_encrypted_message = data.split(":", 1)

                        otp_content = None
                        for identifier, content in self.otp_pages:
                            if identifier == otp_identifier:
                                otp_content = content
                                break

                        if otp_content:
                            decrypted_message = decrypt_message(actual_encrypted_message, otp_content)
                            self.update_chat_area(f"Received from {sender_id} (Decrypted): {decrypted_message}")
                        else:
                            self.update_chat_area(f"Received from {sender_id} (Unknown OTP): {actual_encrypted_message}")
            except Exception as e:
                print("Error:", e)
                if self.client_socket:
                    self.client_socket.close()
                break

    def update_chat_area(self, message):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.yview(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    client_app = OTPClient(root)
    root.mainloop()
