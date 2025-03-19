import tkinter as tk
from tkinter import messagebox
import threading
import socket
import sys

# Dictionary to map user_id -> (ip, port)
clients = {}

def find_user_id_by_addr(addr):
    """Return the user_id corresponding to a specific (ip, port) address, or None if not found."""
    for uid, address in clients.items():
        if address == addr:
            return uid
    return None

class UDPServerThread(threading.Thread):
    def __init__(self, host, port, status_callback):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.status_callback = status_callback
        self.running = False

    def run(self):
        # Create a UDP socket
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            try:
                server_socket.bind((self.host, self.port))
            except Exception as e:
                self.status_callback(f"Error binding server to {self.host}:{self.port} - {e}", error=True)
                return

            self.running = True
            self.status_callback(f"Server listening on UDP {self.host}:{self.port}")

            while self.running:
                try:
                    data, addr = server_socket.recvfrom(4096)
                except OSError:
                    # Socket likely closed
                    break

                if not data:
                    continue

                message = data.decode("utf-8", errors="ignore").strip()


                if message.startswith("CONNECT|"):
                    # Extract user_id from the message
                    parts = message.split("|", maxsplit=1)
                    if len(parts) < 2:
                        continue

                    user_id = parts[1].strip()
                    if not user_id:
                        # Invalid userID
                        server_socket.sendto("ERROR:Invalid userID".encode("utf-8"), addr)
                        continue

                    if user_id in clients:
                        # Already taken
                        server_socket.sendto("ERROR:UserID taken".encode("utf-8"), addr)
                        print(f"Rejected '{addr}': UserID '{user_id}' already taken.")
                        continue

                    # Register this user
                    clients[user_id] = addr
                    server_socket.sendto("CONNECTED".encode("utf-8"), addr)
                    print(f"User '{user_id}' connected from {addr}")

                elif message.startswith("SEND|"):
                    # Format: SEND|recipient_id|<otpIdentifier:encryptedMessage>
                    parts = message.split("|", maxsplit=2)
                    if len(parts) < 3:
                        continue

                    recipient_id = parts[1]
                    content = parts[2]  # "otpIdentifier:encryptedMessage" combined

                    # Identify the sender from 'addr'
                    sender_id = find_user_id_by_addr(addr)
                    if not sender_id:
                        # Not recognized => ignore or send error
                        error_msg = "ERROR:Sender not recognized. Send CONNECT first."
                        server_socket.sendto(error_msg.encode("utf-8"), addr)
                        continue

                    print(f"Received from '{sender_id}' -> '{recipient_id}': {content}")

                    if recipient_id in clients:
                        # Forward to recipient
                        recipient_addr = clients[recipient_id]
                        # Server sends: MSG|sender_id|otpIdentifier:encryptedMessage
                        forward_msg = f"MSG|{sender_id}|{content}"
                        try:
                            server_socket.sendto(forward_msg.encode("utf-8"), recipient_addr)
                            print(f"Forwarded to '{recipient_id}' @ {recipient_addr}")
                        except Exception as e:
                            print(f"Failed to send to '{recipient_id}': {e}")
                            # Possibly remove them
                            del clients[recipient_id]
                    else:
                        # Notify sender that recipient doesn't exist
                        error_msg = f"ERROR:Recipient '{recipient_id}' not found."
                        server_socket.sendto(error_msg.encode("utf-8"), addr)
                        print(error_msg)

                else:
                    # Unknown message => ignore or handle
                    pass

    def stop(self):
        self.running = False
        # Create a dummy datagram to unblock the recvfrom()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as temp_sock:
            temp_sock.sendto(b'', (self.host, self.port))


class ServerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("UDP Server GUI")

        self.HOST = "0.0.0.0"
        self.PORT = 65432

        self.server_thread = None

        # Status label
        self.status_label = tk.Label(master, text="Server is NOT running.", fg="red", font=("Arial", 12))
        self.status_label.pack(pady=5)

        # Start Button
        self.start_button = tk.Button(master, text="Start Server", command=self.start_server, width=15)
        self.start_button.pack(pady=5)

        # Label to display the public address info (filled in manually if needed)
        self.addr_info_label = tk.Label(master, text="", fg="blue", font=("Arial", 10))
        self.addr_info_label.pack(pady=5)

        # Stop Button
        self.stop_button = tk.Button(master, text="Stop Server", command=self.stop_server, width=15, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

    def update_status(self, message, error=False):
        """Helper to update status text in the GUI."""
        self.status_label.config(text=message, fg=("red" if error else "green"))

    def start_server(self):
        """Start the UDP server thread."""
        try:
            # Clear old clients on start
            clients.clear()

            # Start our custom server thread
            self.server_thread = UDPServerThread(self.HOST, self.PORT, self.update_status)
            self.server_thread.start()

            # Update status
            self.update_status("Server is RUNNING.")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

            self.addr_info_label.config(
                text="Run localxpose externally, e.g.\n loclx serve udp --port 65432\nThen share the provided public address."
            )

        except Exception as e:
            messagebox.showerror("Error starting server", str(e))

    def stop_server(self):
        """Stops the server."""
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread = None

        # Update status
        self.update_status("Server is NOT running.", error=True)
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.addr_info_label.config(text="")

def main():
    root = tk.Tk()
    gui = ServerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
