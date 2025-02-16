# otp_voice_server.py

import socket
import threading
import socketserver

HOST = '0.0.0.0'   # Listen on all interfaces
PORT = 65432       # Local port. Expose via ngrok: "ngrok tcp 65432"
clients = {}       # userID -> client_socket

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_socket = self.request
        user_id = None
        try:
            # 1) Read userID from client
            user_id = client_socket.recv(1024).decode("utf-8").strip()
            if not user_id:
                client_socket.sendall("Invalid userID. Connection closed.".encode("utf-8"))
                client_socket.close()
                return

            # 2) Check if userID is already in use
            if user_id in clients:
                client_socket.sendall("UserID already taken. Connection closed.".encode("utf-8"))
                client_socket.close()
                print(f"Rejected connection from {self.client_address}: UserID '{user_id}' already taken.")
                return

            # 3) Store the socket
            clients[user_id] = client_socket
            client_socket.sendall("Connected successfully.".encode("utf-8"))
            print(f"User '{user_id}' connected from {self.client_address}")

            # 4) Continuously read forwarded audio data
            while True:
                message = client_socket.recv(8192).decode("utf-8")
                if not message:
                    # Client disconnected
                    break

                # Expected format: "recipientID|OTP_ID:ENC_CHUNK_IN_HEX"
                try:
                    recipient_id, payload = message.split("|", 1)
                    print(f"Received audio chunk for '{recipient_id}' from '{user_id}'.")
                    forward_to_recipient(recipient_id, payload, user_id)
                except ValueError:
                    client_socket.sendall("Invalid chunk format.".encode("utf-8"))

        except Exception as e:
            print(f"Error handling {self.client_address}: {e}")
        finally:
            # Remove from clients on disconnect
            if user_id in clients:
                del clients[user_id]
                print(f"User '{user_id}' disconnected.")
            client_socket.close()

def forward_to_recipient(recipient_id, payload, sender_id):
    """
    Forward the incoming payload (OTP_ID:ENC_CHUNK) to recipient_id if connected.
    """
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        try:
            # Format: "senderID|OTP_ID:ENC_CHUNK"
            full_message = f"{sender_id}|{payload}"
            recipient_socket.sendall(full_message.encode("utf-8"))
        except Exception as e:
            print(f"Failed to send audio chunk to '{recipient_id}': {e}")
            del clients[recipient_id]
            recipient_socket.close()
    else:
        # If recipient not connected, optionally notify the sender
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
        print(f"Voice OTP Server running on {ip}:{port}\n"
              f"Expose it via ngrok: `ngrok tcp {port}` (Ctrl+C to stop)")

        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
            server.server_close()
