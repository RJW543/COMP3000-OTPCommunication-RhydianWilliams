import socket
import threading
import socketserver
import subprocess
import time
import re
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 65432
clients = {}  # userID -> client_socket mapping

NGROK_HOST = None
NGROK_PORT = None

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_socket = self.request
        user_id = client_socket.recv(1024).decode("utf-8").strip()
        if user_id in clients:
            client_socket.sendall("UserID already taken. Connection closed.".encode("utf-8"))
            client_socket.close()
            return

        clients[user_id] = client_socket
        client_socket.sendall("Connected successfully.".encode("utf-8"))
        print(f"User {user_id} connected from {self.client_address}")

        # Handle incoming messages
        while True:
            try:
                message = client_socket.recv(1024).decode("utf-8")
                if message:
                    recipient_id, encrypted_message = message.split("|", 1)
                    print(f"Received message for {recipient_id} from {user_id}: {encrypted_message}")
                    send_message_to_recipient(recipient_id, encrypted_message, user_id)
            except:
                print(f"Connection lost for user {user_id}.")
                clients.pop(user_id, None)
                client_socket.close()
                break

def send_message_to_recipient(recipient_id, message, sender_id):
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        try:
            full_message = f"{sender_id}|{message}"
            recipient_socket.send(full_message.encode("utf-8"))
        except:
            print(f"Failed to send message to {recipient_id}. Removing client.")
            clients.pop(recipient_id, None)
            recipient_socket.close()

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

# Simple HTTP handler to serve the Ngrok info
class NgrokInfoHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/ngrok':
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            info = {
                "host": NGROK_HOST,
                "port": NGROK_PORT
            }
            self.wfile.write(json.dumps(info).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_http_server():
    http_server = HTTPServer((HOST, 5000), NgrokInfoHandler)
    print("HTTP server for Ngrok info running on port 5000")
    http_server.serve_forever()

def start_ngrok():
    # Start ngrok to tunnel the TCP server port
    print("Starting Ngrok...")
    ngrok = subprocess.Popen(['ngrok', 'tcp', str(PORT)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # Wait a bit for ngrok to initialize
    time.sleep(5)

    # Fetch ngrok tunnel info from localhost:4040 API
    try:
        res = requests.get("http://localhost:4040/api/tunnels")
        tunnels = res.json()
        for t in tunnels.get("tunnels", []):
            if t.get("proto") == "tcp":
                public_url = t.get("public_url")
                # public_url format: tcp://0.tcp.ngrok.io:12345
                global NGROK_HOST, NGROK_PORT
                # Extract host and port
                url = public_url.replace("tcp://", "")
                NGROK_HOST, NGROK_PORT = url.split(":")
                print(f"Ngrok address: {NGROK_HOST}:{NGROK_PORT}")
                break
    except Exception as e:
        print("Error fetching Ngrok info:", e)

    return ngrok

if __name__ == "__main__":
    # Start the Ngrok tunnel
    ngrok_process = start_ngrok()

    # Start the server
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Server running on {HOST}:{PORT} and accessible via Ngrok...")

    # Start HTTP server to serve Ngrok info
    http_thread = threading.Thread(target=run_http_server, daemon=True)
    http_thread.start()

    # Keep main thread alive
    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("Shutting down the server...")
        server.shutdown()
        server.server_close()
        if ngrok_process:
            ngrok_process.terminate()
