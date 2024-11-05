# File: otp_client_internet.py
import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
from pathlib import Path
import msvcrt

SERVER_HOST = '141.163.53.214'  # Replace 'public_ip_here' 
SERVER_PORT = 65432

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

def get_next_otp_page_windows(otp_pages, used_identifiers, lock_file="used_pages.lock"):
    """Find the next unused OTP page based on identifiers with a locking mechanism on Windows."""
    with open(lock_file, "w") as lock:
        msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)  # Acquire an exclusive lock

        for identifier, content in otp_pages:
            if identifier not in used_identifiers:
                # Mark it as used immediately
                save_used_page(identifier)
                used_identifiers.add(identifier)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)  # Release the lock
                return identifier, content

        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)  # Release the lock if no match found
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

        # Load OTP pages
        self.otp_pages = load_otp_pages()
        self.used_identifiers = load_used_pages()

        # GUI setup for user ID
        self.user_id_frame = tk.Frame(master)
        self.user_id_frame.pack(padx=10, pady=10)

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

        self.client_socket = None
        self.send_button.pack()

    def connect_to_server(self):
        self.user_id = self.user_id_entry.get()
        if not self.user_id:
            messagebox.showwarning("Warning", "Please enter a userID.")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((SERVER_HOST, SERVER_PORT))
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
            receive_thread = threading.Thread(target=self.receive_messages)
            receive_thread.daemon = True
            receive_thread.start()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to the server: {e}")

    def get_next_available_otp(self):
        return get_next_otp_page_windows(self.otp_pages, self.used_identifiers)

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
            # Send the recipient ID along with the OTP identifier and the encrypted message
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
                        # Expect the message format to be "sender_id|otp_identifier:encrypted_message"
                        sender_id, data = message.split("|", 1)
                        otp_identifier, actual_encrypted_message = data.split(":", 1)
                        
                        # Find the corresponding OTP content for decryption
                        otp_content = None
                        for identifier, content in self.otp_pages:
                            if identifier == otp_identifier:
                                otp_content = content
                                break
                        
                        if otp_content:
                            decrypted_message = decrypt_message(actual_encrypted_message, otp_content)
                            self.update_chat_area(f"Received from {sender_id} (Decrypted): {decrypted_message}")
                        else:
                            # If OTP identifier not found, display raw encrypted message
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

# Start the GUI client
if __name__ == "__main__":
    root = tk.Tk()
    client_app = OTPClient(root)
    root.mainloop()
