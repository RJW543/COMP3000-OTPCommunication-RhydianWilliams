import socket
import threading
import socketserver
from pyngrok import ngrok

HOST = '0.0.0.0'
PORT = 65432

clients = {}  # Maps userID -> (socket)

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    """
    Each client connection is handled in a separate thread.
    Do line-based reading from the socket to handle partial receives.
    """
    def handle(self):
        client_socket = self.request
        user_id = None
        buffer = ""  # Accumulate partial data here

        try:
            while True:
                data = client_socket.recv(4096)
                if not data:
                    # Socket closed
                    break

                buffer += data.decode("utf-8", errors="replace")

                # Process any full lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue

                    if user_id is None:
                        # The first line we receive is the userID
                        user_id = self.handle_user_id(line, client_socket)
                        if not user_id:
                            return  # Invalid or duplicate userID -> connection closed
                    else:
                        # Subsequent lines are audio chunks:
                        self.handle_audio_chunk(line, user_id)
        except Exception as e:
            print(f"Error with client {self.client_address}: {e}")
        finally:
            # Clean up on disconnect
            if user_id in clients:
                del clients[user_id]
                print(f"User '{user_id}' disconnected.")
            client_socket.close()

    def handle_user_id(self, line, client_socket):
        """
        The first line from the client is their userID.
        Check if already taken, if so, close connection.
        Otherwise, store them and return user_id.
        """
        user_id = line.strip()
        if not user_id:
            client_socket.sendall(b"Invalid userID.\n")
            client_socket.close()
            return None

        if user_id in clients:
            msg = "UserID already taken. Connection closed.\n"
            client_socket.sendall(msg.encode("utf-8"))
            client_socket.close()
            print(f"Rejected connection {self.client_address}: userID '{user_id}' taken.")
            return None

        # Accept and store
        clients[user_id] = client_socket
        client_socket.sendall(b"Connected successfully.\n")
        print(f"User '{user_id}' connected from {self.client_address}")
        return user_id

    def handle_audio_chunk(self, line, sender_id):
        """
        line format: "recipientID|otpIdentifier:hexData"
        We'll forward it to recipient.
        """
        if "|" not in line or ":" not in line:
            # Invalid format
            self.request.sendall(b"Invalid chunk format.\n")
            return

        try:
            recipient_id, payload = line.split("|", 1)
            # payload format: "otpID:encryptedHex"
        except ValueError:
            self.request.sendall(b"Invalid chunk format.\n")
            return

        print(f"Received audio chunk for '{recipient_id}' from '{sender_id}'.")
        forward_to_recipient(recipient_id, payload, sender_id)

def forward_to_recipient(recipient_id, payload, sender_id):
    """
    Forward the line "sender_id|otpID:hexData" to recipient if connected.
    We'll send it as: "senderID|otpID:hexData\n" (with a newline).
    """
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        try:
            full_line = f"{sender_id}|{payload}\n"
            recipient_socket.sendall(full_line.encode("utf-8"))
        except Exception as e:
            print(f"Failed to send audio to '{recipient_id}': {e}")
            # Remove from clients
            if recipient_id in clients:
                del clients[recipient_id]
            recipient_socket.close()
    else:
        # Optionally tell sender "not found"
        sender_socket = clients.get(sender_id)
        if sender_socket:
            msg = f"Recipient '{recipient_id}' not found.\n"
            sender_socket.sendall(msg.encode("utf-8"))
        print(f"User '{sender_id}' tried to send audio to unknown recipient '{recipient_id}'.")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    # Create server
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)

    # Start pyngrok tunnel (tcp)
    public_url = ngrok.connect(PORT, "tcp")
    print("PyNgrok tunnel open! Access info:")
    print(" Public URL:", public_url.public_url)

    with server:
        ip, port = server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(f"Local server running on {ip}:{port} (Ctrl+C to stop)")

        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
            server.server_close()
