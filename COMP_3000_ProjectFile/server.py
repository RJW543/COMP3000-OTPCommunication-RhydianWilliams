"""
server.py

A forwarding server for real-time OTP-encrypted voice calls.
Clients connect and send a JSON login message (with "user_id" and "target_id").
After login, each client sends fixed-size encrypted voice chunks.
The server forwards each voice chunk to the intended target client.

This server also uses pyngrok to expose a public TCP endpoint.
"""

import socket
import threading
import json
from pyngrok import ngrok

# Constants
CHUNK_SIZE = 2048     # Size (in bytes) of each voice chunk

# Global dictionary mapping user_id -> (socket, target_id)
clients = {}

def recv_all(sock, n):
    """Helper to receive exactly n bytes from a socket."""
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def handle_client(conn, addr):
    global clients
    user_id = None
    try:
        # Read login message (JSON terminated by newline)
        login_data = b''
        while not login_data.endswith(b'\n'):
            chunk = conn.recv(1)
            if not chunk:
                return
            login_data += chunk
        login_info = json.loads(login_data.decode('utf-8').strip())
        user_id = login_info.get("user_id")
        target_id = login_info.get("target_id")
        if not user_id or not target_id:
            print("Invalid login message from", addr)
            conn.close()
            return

        print(f"User '{user_id}' connected from {addr}, targeting '{target_id}'")
        clients[user_id] = (conn, target_id)

        while True:
            # Read exactly CHUNK_SIZE bytes from the client
            data = recv_all(conn, CHUNK_SIZE)
            if data is None:
                print(f"User '{user_id}' disconnected.")
                break
            # Forward the chunk to the target if available
            if target_id in clients:
                target_conn, _ = clients[target_id]
                try:
                    target_conn.sendall(data)
                except Exception as e:
                    print(f"Error sending data to '{target_id}': {e}")
            else:
                print(f"Target '{target_id}' not connected. Dropping packet.")
    except Exception as e:
        print(f"Exception handling client {addr}: {e}")
    finally:
        conn.close()
        if user_id and user_id in clients:
            del clients[user_id]

def main():
    port = 12345
    # Expose the server using Ngrok 
    tunnel = ngrok.connect(port, "tcp")
    public_url = tunnel.public_url
    print("Ngrok tunnel established at:", public_url)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', port))
    server_socket.listen(5)
    print("Server listening on port", port)

    try:
        while True:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("Server shutting down.")
    finally:
        server_socket.close()
        ngrok.disconnect(public_url)

if __name__ == "__main__":
    main()
