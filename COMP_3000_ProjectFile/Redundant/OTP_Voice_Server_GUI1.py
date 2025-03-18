#!/usr/bin/env python3
"""

A forwarding server for real-time OTP-encrypted voice calls.
Clients connect via Ngrok and send a login message in the format:
    user_id|recipient_id\n
After login, clients send fixed-size binary audio chunks (2048 bytes)
that the server forwards to the intended recipient.

This server uses pyngrok to expose a public TCP endpoint.
"""

import socket
import threading
import socketserver
from pyngrok import ngrok

CHUNK_SIZE = 2048  # Fixed binary voice chunk size

# Global dictionary mapping user_id -> (socket, recipient_id)
clients = {}

def recv_all(sock, n):
    """Helper function to receive exactly n bytes from a socket."""
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

class VoiceRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_socket = self.request
        user_id = None
        try:
            # Read login message (terminated by newline)
            login_data = b""
            while not login_data.endswith(b"\n"):
                chunk = client_socket.recv(1)
                if not chunk:
                    return
                login_data += chunk
            login_str = login_data.decode("utf-8").strip()
            if "|" not in login_str:
                client_socket.sendall("Invalid login format.\n".encode("utf-8"))
                client_socket.close()
                return
            user_id, recipient_id = login_str.split("|", 1)
            if user_id in clients:
                client_socket.sendall("UserID already taken.\n".encode("utf-8"))
                client_socket.close()
                return
            clients[user_id] = (client_socket, recipient_id)
            client_socket.sendall("Connected.\n".encode("utf-8"))
            print(f"User '{user_id}' connected, targeting '{recipient_id}'")

            # Continuously receive and forward fixed-size audio chunks
            while True:
                data = recv_all(client_socket, CHUNK_SIZE)
                if data is None:
                    break  # Client disconnected
                if recipient_id in clients:
                    target_socket, _ = clients[recipient_id]
                    try:
                        target_socket.sendall(data)
                    except Exception as e:
                        print(f"Error forwarding data to '{recipient_id}': {e}")
                else:
                    print(f"Recipient '{recipient_id}' not connected. Dropping audio chunk.")
        except Exception as e:
            print(f"Exception handling client: {e}")
        finally:
            if user_id in clients:
                del clients[user_id]
                print(f"User '{user_id}' disconnected.")
            client_socket.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

def main():
    HOST = "0.0.0.0"
    PORT = 65432

    # Expose the server with Ngrok 
    tunnel = ngrok.connect(PORT, "tcp")
    public_url = tunnel.public_url
    print(f"Ngrok tunnel established at: {public_url}")

    server = ThreadedTCPServer((HOST, PORT), VoiceRequestHandler)
    with server:
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        print(f"Voice server running on {HOST}:{PORT}")
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("Shutting down server...")
            server.shutdown()
            server.server_close()
            ngrok.disconnect(public_url)

if __name__ == "__main__":
    main()
