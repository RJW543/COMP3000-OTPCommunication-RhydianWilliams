import tkinter as tk
from tkinter import messagebox
import threading
import socket
import socketserver
from pyngrok import ngrok
from collections import defaultdict

clients = {}  # user_id -> client_socket

pending_messages = defaultdict(list)  

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_socket = self.request
        user_id = None
        try:
            # 1. Receive the user_id
            user_id = client_socket.recv(1024).decode("utf-8").strip()
            if not user_id:
                client_socket.sendall("Invalid userID. Connection closed.".encode("utf-8"))
                client_socket.close()
                return

            # 2. Check if this user_id is already in use (i.e., a currently connected user)
            if user_id in clients:
                client_socket.sendall("UserID already taken. Connection closed.".encode("utf-8"))
                client_socket.close()
                print(f"Rejected connection from {self.client_address}: UserID '{user_id}' already taken.")
                return

            # 3. Register the client as "connected"
            clients[user_id] = client_socket
            client_socket.sendall("Connected successfully.".encode("utf-8"))
            print(f"User '{user_id}' connected from {self.client_address}")

            # 4. Deliver any pending messages for this user
            if user_id in pending_messages and pending_messages[user_id]:
                for (sender, msg) in pending_messages[user_id]:
                    full_message = f"{sender}|{msg}"
                    client_socket.sendall(full_message.encode("utf-8"))
                # Clear them out once delivered
                del pending_messages[user_id]
                print(f"Delivered pending messages to '{user_id}'.")

            # 5. Handle incoming messages from this client
            while True:
                data = client_socket.recv(4096)
                if not data:
                    break  # client disconnected
                message = data.decode("utf-8")

                try:
                    recipient_id, encrypted_message = message.split("|", 1)
                    print(f"Received message for '{recipient_id}' from '{user_id}': {encrypted_message}")
                    send_message_to_recipient(recipient_id, encrypted_message, user_id)
                except ValueError:
                    client_socket.sendall("Invalid message format.".encode("utf-8"))

        except Exception as e:
            print(f"Error handling client {self.client_address}: {e}")
        finally:
            # 6. Cleanup: remove this user from `clients` if they are disconnecting
            if user_id and user_id in clients:
                del clients[user_id]
                print(f"User '{user_id}' disconnected.")
            client_socket.close()


def send_message_to_recipient(recipient_id, message, sender_id):
    """Attempt to deliver `message` from `sender_id` to `recipient_id`."""
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        # The recipient is connected, so deliver immediately
        try:
            full_message = f"{sender_id}|{message}"
            recipient_socket.sendall(full_message.encode("utf-8"))
            print(f"Forwarded message from '{sender_id}' to '{recipient_id}'.")
        except Exception as e:
            print(f"Failed to send message to '{recipient_id}': {e}")
            # If there's a failure, remove them and store the message pending
            if recipient_id in clients:
                del clients[recipient_id]
            pending_messages[recipient_id].append((sender_id, message))
            recipient_socket.close()
    else:
        # The recipient is NOT currently connected -> queue the message
        pending_messages[recipient_id].append((sender_id, message))
        print(f"User '{sender_id}' sent message to offline user '{recipient_id}'. Queued for later.")


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


class ServerGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Server GUI")

        self.HOST = "0.0.0.0"
        self.PORT = 65432

        self.server = None
        self.server_thread = None
        self.ngrok_tunnel = None

        # Status label
        self.status_label = tk.Label(master, text="Server is NOT running.", fg="red", font=("Arial", 12))
        self.status_label.pack(pady=5)

        # Start Button
        self.start_button = tk.Button(master, text="Start Server", command=self.start_server, width=15)
        self.start_button.pack(pady=5)

        # Label to display the public NGROK info
        self.ngrok_info_label = tk.Label(master, text="", fg="blue", font=("Arial", 10))
        self.ngrok_info_label.pack(pady=5)

        # Stop Button
        self.stop_button = tk.Button(master, text="Stop Server", command=self.stop_server, width=15, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

    def start_server(self):
        """Starts the Ngrok tunnel and the ThreadedTCPServer in a background thread."""
        try:
            self.ngrok_tunnel = ngrok.connect(self.PORT, "tcp")
            public_url = self.ngrok_tunnel.public_url

            # Parse host and port from the public URL
            parsed_url = public_url.replace("tcp://", "").split(":")
            ngrok_host = parsed_url[0]
            ngrok_port = parsed_url[1]

            # Update the label to show the ngrok info
            self.ngrok_info_label.config(
                text=f"Public URL: {public_url}\nNgrok Host: {ngrok_host}\nNgrok Port: {ngrok_port}"
            )

            def run_server():
                self.server = ThreadedTCPServer((self.HOST, self.PORT), ThreadedTCPRequestHandler)
                with self.server:
                    ip, port = self.server.server_address
                    print(f"Local server running on {ip}:{port}.")
                    self.server.serve_forever()

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()

            self.status_label.config(text="Server is RUNNING.", fg="green")
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Error starting server", str(e))

    def stop_server(self):
        """Stops the server and closes the ngrok tunnel."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
                print("Server has been stopped.")
            except Exception as e:
                print(f"Error stopping server: {e}")

        if self.ngrok_tunnel:
            try:
                ngrok.disconnect(self.ngrok_tunnel.public_url)
                print("Ngrok tunnel disconnected.")
            except Exception as e:
                print(f"Error disconnecting ngrok tunnel: {e}")

        self.server = None
        self.server_thread = None
        self.ngrok_tunnel = None

        self.status_label.config(text="Server is NOT running.", fg="red")
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.ngrok_info_label.config(text="")


def main():
    root = tk.Tk()
    gui = ServerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
