import tkinter as tk
from tkinter import messagebox, scrolledtext
import socket
import threading
import sys
import fcntl
from pathlib import Path

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
        self.master.title("OTP Messaging Client (UDP)")

        # Initialise OTP
        self.otp_pages = load_otp_pages()
        self.used_identifiers = load_used_pages()

        # Frame for LocalXpose public address input
        self.addr_frame = tk.Frame(master)
        self.addr_frame.pack(padx=10, pady=5)

        self.host_label = tk.Label(self.addr_frame, text="Host:")
        self.host_label.pack(side=tk.LEFT, padx=(0, 5))

        self.host_entry = tk.Entry(self.addr_frame, width=25)
        self.host_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.host_entry.insert(0, "xyz.loclx.io")  # Example placeholder

        self.port_label = tk.Label(self.addr_frame, text="Port:")
        self.port_label.pack(side=tk.LEFT, padx=(0, 5))

        self.port_entry = tk.Entry(self.addr_frame, width=10)
        self.port_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.port_entry.insert(0, "12345")  # Example placeholder

        self.set_server_button = tk.Button(self.addr_frame, text="Set Server", command=self.set_server_address)
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

        # Label + Entry for Recipient userID
        self.recipient_label = tk.Label(self.message_frame, text="Recipient userID:")
        self.recipient_label.pack()
        self.recipient_input = tk.Entry(self.message_frame, width=50)
        self.recipient_input.pack(pady=5)

        # Label + Entry for the message text
        self.message_label = tk.Label(self.message_frame, text="Message to send:")
        self.message_label.pack()
        self.text_input = tk.Entry(self.message_frame, width=50)
        self.text_input.pack(pady=5)

        self.send_button = tk.Button(self.message_frame, text="Send", command=self.send_message)
        self.send_button.pack()

        self.client_socket = None

        # Server address variables
        self.SERVER_HOST = None
        self.SERVER_PORT = None
        self.user_id = None

        # Threading control
        self.stop_receiving = False
        self.receive_thread = None

    def set_server_address(self):
        host = self.host_entry.get().strip()
        port = self.port_entry.get().strip()
        if not host or not port:
            messagebox.showwarning("Warning", "Please enter both host and port.")
            return
        if not port.isdigit():
            messagebox.showwarning("Warning", "Port must be a number.")
            return

        self.SERVER_HOST = host
        self.SERVER_PORT = int(port)
        messagebox.showinfo("Info", f"Server address set to {self.SERVER_HOST}:{self.SERVER_PORT}")

        # Enable the user ID frame
        self.user_id_frame.pack(padx=10, pady=10)
        # Disable these fields
        self.host_entry.config(state=tk.DISABLED)
        self.port_entry.config(state=tk.DISABLED)
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
            # Create a UDP socket
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.client_socket.settimeout(5.0)  # For handshake wait

            # Send handshake: CONNECT|userID
            handshake_msg = f"CONNECT|{self.user_id}"
            self.client_socket.sendto(handshake_msg.encode("utf-8"), (self.SERVER_HOST, self.SERVER_PORT))

            # Wait for response
            data, _ = self.client_socket.recvfrom(1024)
            response = data.decode("utf-8", errors="ignore")
            if response == "CONNECTED":
                messagebox.showinfo("Info", "Connected to the server via UDP.")
                self.user_id_frame.pack_forget()
                self.message_frame.pack(padx=10, pady=10)
                self.user_id_display.config(text=f"Your userID: {self.user_id}")

                # Start a background thread to receive incoming messages
                self.stop_receiving = False
                self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
                self.receive_thread.start()
            elif response.startswith("ERROR:"):
                messagebox.showerror("Error", response)
                self.client_socket.close()
                self.client_socket = None
            else:
                messagebox.showerror("Error", f"Unexpected response: {response}")
                self.client_socket.close()
                self.client_socket = None
        except socket.timeout:
            messagebox.showerror("Error", "No response from server. Check LocalXpose address or server status.")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect: {e}")
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None

    def get_next_available_otp(self):
        return get_next_otp_page_linux(self.otp_pages, self.used_identifiers)

    def send_message(self):
        if not self.client_socket:
            messagebox.showwarning("Warning", "You are not connected to the server.")
            return

        recipient_id = self.recipient_input.get().strip()
        message = self.text_input.get()

        if not recipient_id:
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
            full_message = f"SEND|{recipient_id}|{otp_identifier}:{encrypted_message}"

            try:
                self.client_socket.sendto(full_message.encode("utf-8"), (self.SERVER_HOST, self.SERVER_PORT))
                self.text_input.delete(0, tk.END)
                self.update_chat_area(f"Me (Encrypted to {recipient_id}): {encrypted_message}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to send message: {e}")
        else:
            messagebox.showerror("Error", "No available OTP pages to use.")

    def receive_messages(self):
        self.client_socket.settimeout(1.0)  # So we can periodically check for stop_receiving
        while not self.stop_receiving:
            try:
                data, _ = self.client_socket.recvfrom(4096)
                if not data:
                    continue

                message = data.decode("utf-8", errors="ignore")
                
                if message.startswith("MSG|"):
                    try:
                        parts = message.split("|", maxsplit=2)
                        if len(parts) < 3:
                            continue

                        sender_id = parts[1]
                        payload = parts[2]  # Expected format: otpIdentifier:encryptedMessage
                        if ":" in payload:
                            otp_identifier, actual_encrypted_message = payload.split(":", maxsplit=1)

                            # Find the matching OTP content
                            otp_content = None
                            for identifier, content in self.otp_pages:
                                if identifier == otp_identifier:
                                    otp_content = content
                                    break

                            if otp_content:
                                decrypted_message = decrypt_message(actual_encrypted_message, otp_content)
                                display_message = f"Received from {sender_id} (Decrypted): {decrypted_message}"
                            else:
                                display_message = f"Received from {sender_id} (Unknown OTP): {actual_encrypted_message}"
                        else:
                            # If no colon is found, just display the raw payload.
                            display_message = f"Received from {sender_id}: {payload}"

                        # Schedule GUI update on the main thread:
                        self.master.after(0, lambda msg=display_message: self.update_chat_area(msg))
                    except Exception as e:
                        self.master.after(0, lambda: self.update_chat_area("Received improperly formatted MSG."))
                elif message.startswith("ERROR:"):
                    self.master.after(0, lambda: self.update_chat_area(f"Server Error: {message}"))
                else:
                    # Optionally handle unexpected message formats
                    pass

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Error receiving: {e}")
                break

        # If loop exits, close socket and warn the user
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
        self.master.after(0, lambda: messagebox.showwarning("Warning", "Disconnected from server."))
        self.master.after(0, self.master.quit)


    def update_chat_area(self, msg):
        self.chat_area.config(state=tk.NORMAL)
        self.chat_area.insert(tk.END, msg + "\n")
        self.chat_area.config(state=tk.DISABLED)
        self.chat_area.yview(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    client_app = OTPClient(root)
    root.mainloop()
