# otp_client_internet3.py
import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
from pathlib import Path
import fcntl

# --- OTP Related Functions ---

def load_otp_pages(file_name="otp_cipher.txt"):
    otp_pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        return otp_pages
    with file_path.open("r") as file:
        for line in file:
            if len(line) < 8:
                continue  # Skip invalid lines
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
    """Find the next unused OTP page based on identifiers with a locking mechanism on Linux."""
    with open(lock_file, "w") as lock:
        # Acquire an exclusive lock
        fcntl.flock(lock, fcntl.LOCK_EX)

        for identifier, content in otp_pages:
            if identifier not in used_identifiers:
                # Mark it as used immediately
                save_used_page(identifier)
                used_identifiers.add(identifier)
                # Release the lock before returning
                fcntl.flock(lock, fcntl.LOCK_UN)
                return identifier, content

        # Release the lock if no match found
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

        # Initialize OTP
        self.otp_pages = load_otp_pages()
        self.used_identifiers = load_used_pages()

        # Frame for Ngrok address input
        self.ngrok_frame = tk.Frame(master)
        self.ngrok_frame.pack(padx=10, pady=5)

        self.ngrok_host_label = tk.Label(self.ngrok_frame, text="Ngrok Host:")
        self.ngrok_host_label.pack(side=tk.LEFT, padx=(0, 5))

        self.ngrok_host_entry = tk.Entry(self.ngrok_frame, width=25)
        self.ngrok_host_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.ngrok_host_entry.insert(0, "0.tcp.ngrok.io")  # Default placeholder

        self.ngrok_port_label = tk.Label(self.ngrok_frame, text="Ngrok Port:")
        self.ngrok_port_label.pack(side=tk.LEFT, padx=(0, 5))

        self.ngrok_port_entry = tk.Entry(self.ngrok_frame, width=10)
        self.ngrok_port_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.ngrok_port_entry.insert(0, "12345")  # Default placeholder

        self.set_server_button = tk.Button(self.ngrok_frame, text="Set Server Address", command=self.set_server_address)
        self.set_server_button.pack(side=tk.LEFT)

        # Frame for user ID
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

        # Initialize server address variables
        self.SERVER_HOST = None
        self.SERVER_PORT = None
    
    def set_server_address(self):
        host = self.ngrok_host_entry.get().strip()
        port = self.ngrok_port_entry.get().strip()
        if not host or not port:
            messagebox.showwarning("Warning", "Please enter both Ngrok host and port.")
            return
        if not port.isdigit():
            messagebox.showwarning("Warning", "Port must be a number.")
            return
        self.SERVER_HOST = host
        self.SERVER_PORT = int(port)
        messagebox.showinfo("Info", f"Server address set to {self.SERVER_HOST}:{self.SERVER_PORT}")
        # Enable the user ID frame
        self.user_id_frame.pack(padx=10, pady=10)
        # Disable the Ngrok input fields to prevent changes after setting
        self.ngrok_host_entry.config(state=tk.DISABLED)
        self.ngrok_port_entry.config(state=tk.DISABLED)
        self.set_server_button.config(state=tk.DISABLED)
    
    def connect_to_server(self):
        if self.SERVER_HOST is None or self.SERVER_PORT is None:
            messagebox.showwarning("Warning", "Please set the server address first.")
            return

        self.user_id = self.user_id_entry.get().strip()
        if not self.user_id:
            messagebox.showwarning("Warning", "Please enter a userID.")
            return
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.SERVER_HOST, self.SERVER_PORT))
            self.client_socket.sendall(self.user_id.encode("utf-8"))
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
        if not recipient_id or recipient_id == "Enter recipient userID:":
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
                try:
                    self.client_socket.sendall(full_message.encode("utf-8"))
                    self.text_input.delete(0, tk.END)
                    self.update_chat_area(f"Me (Encrypted to {recipient_id}): {encrypted_message}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to send message: {e}")
        else:
            messagebox.showerror("Error", "No available OTP pages to use.")
    
    def receive_messages(self):
        while True:
            try:
                if self.client_socket:
                    message = self.client_socket.recv(4096).decode("utf-8")
                    if not message:
                        break  # Server disconnected
                    # Expect the message format: "sender_id|otp_identifier:encrypted_message"
                    try:
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
                            
                            # Mark this page as used after decryption to ensure it's never reused.
                            save_used_page(otp_identifier)
                            self.used_identifiers.add(otp_identifier)
                        else:
                            # If no matching OTP identifier found, just show the encrypted message
                            self.update_chat_area(f"Received from {sender_id} (Unknown OTP): {actual_encrypted_message}")
                    except ValueError:
                        self.update_chat_area("Received an improperly formatted message.")
            except Exception as e:
                print(f"Error receiving message: {e}")
                break
        # If the loop breaks, close the socket
        if self.client_socket:
            self.client_socket.close()
        messagebox.showwarning("Warning", "Disconnected from the server.")
        self.master.quit()

    def update_chat_area(self, message):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, message + "\n")
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.yview(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    client_app = OTPClient(root)
    root.mainloop()
