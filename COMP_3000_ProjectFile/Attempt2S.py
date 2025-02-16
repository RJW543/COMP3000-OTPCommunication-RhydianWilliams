import socket
import threading
import socketserver

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 65432
clients = {}      # userID -> client_socket mapping

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_socket = self.request
        user_id = None
        try:
            # 1) Client sends its userID first
            user_id = client_socket.recv(1024).decode("utf-8").strip()
            if not user_id:
                client_socket.sendall("Invalid userID. Connection closed.".encode("utf-8"))
                client_socket.close()
                return

            # 2) Check if userID is already taken
            if user_id in clients:
                client_socket.sendall("UserID already taken. Connection closed.".encode("utf-8"))
                client_socket.close()
                print(f"Rejected connection from {self.client_address}: UserID '{user_id}' already taken.")
                return

            # 3) Store in global dictionary
            clients[user_id] = client_socket
            client_socket.sendall("Connected successfully.".encode("utf-8"))
            print(f"User '{user_id}' connected from {self.client_address}")

            # 4) Handle incoming audio data
            while True:
                message = client_socket.recv(8192).decode("utf-8")
                if not message:
                    # Client disconnected or error
                    break

                # Expected format: "recipientID|otpIdentifier:encryptedHex"
                try:
                    recipient_id, payload = message.split("|", 1)
                    print(f"Received audio for '{recipient_id}' from '{user_id}'.")
                    forward_to_recipient(recipient_id, payload, user_id)
                except ValueError:
                    client_socket.sendall("Invalid chunk format.".encode("utf-8"))

        except Exception as e:
            print(f"Error handling {self.client_address}: {e}")
        finally:
            # Clean up on disconnect
            if user_id in clients:
                del clients[user_id]
                print(f"User '{user_id}' disconnected.")
            client_socket.close()

def forward_to_recipient(recipient_id, payload, sender_id):
    """
    Forward "otpIdentifier:encryptedHex" to the recipient if online.
    We'll send back: "senderID|otpIdentifier:encryptedHex".
    """
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        try:
            full_message = f"{sender_id}|{payload}"
            recipient_socket.sendall(full_message.encode("utf-8"))
        except Exception as e:
            print(f"Failed to send audio to '{recipient_id}': {e}")
            del clients[recipient_id]
            recipient_socket.close()
    else:
        # Optionally notify sender if recipient not found
        sender_socket = clients.get(sender_id)
        if sender_socket:
            msg = f"Recipient '{recipient_id}' not found or not connected."
            sender_socket.sendall(msg.encode("utf-8"))
            print(f"User '{sender_id}' tried to send audio to unknown recipient '{recipient_id}'.")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        ip, port = server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(f"OTP Voice Server running on {ip}:{port}")
        print("Expose it with ngrok via `ngrok tcp 65432`\nPress Ctrl+C to stop.")

        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
            server.server_close()
