# otp_server_host3.py
import socket
import threading
import socketserver
from pyngrok import ngrok

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 65432
clients = {}  # userID -> client_socket mapping

class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_socket = self.request
        user_id = None
        try:
            # Receive the userID upon connect
            user_id = client_socket.recv(1024).decode("utf-8").strip()
            if not user_id:
                client_socket.sendall("Invalid userID. Connection closed.".encode("utf-8"))
                client_socket.close()
                return

            if user_id in clients:
                client_socket.sendall("UserID already taken. Connection closed.".encode("utf-8"))
                client_socket.close()
                print(f"Rejected connection from {self.client_address}: UserID '{user_id}' already taken.")
                return

            # Register the client
            clients[user_id] = client_socket
            client_socket.sendall("Connected successfully.".encode("utf-8"))
            print(f"User '{user_id}' connected from {self.client_address}")

            # Handle incoming messages from this client
            while True:
                message = client_socket.recv(4096).decode("utf-8")
                if not message:
                    break  # Client disconnected

                try:
                    recipient_id, encrypted_message = message.split("|", 1)
                    print(f"Received message for '{recipient_id}' from '{user_id}': {encrypted_message}")
                    send_message_to_recipient(recipient_id, encrypted_message, user_id)
                except ValueError:
                    client_socket.sendall("Invalid message format.".encode("utf-8"))

        except Exception as e:
            print(f"Error handling client {self.client_address}: {e}")
        finally:
            # Clean up on disconnect
            if user_id and user_id in clients:
                del clients[user_id]
                print(f"User '{user_id}' disconnected.")
            client_socket.close()

def send_message_to_recipient(recipient_id, message, sender_id):
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        try:
            full_message = f"{sender_id}|{message}"
            recipient_socket.sendall(full_message.encode("utf-8"))
            print(f"Forwarded message from '{sender_id}' to '{recipient_id}'.")
        except Exception as e:
            print(f"Failed to send message to '{recipient_id}': {e}")
            del clients[recipient_id]
            recipient_socket.close()
    else:
        # Notify the sender that the recipient doesn't exist
        sender_socket = clients.get(sender_id)
        if sender_socket:
            sender_socket.sendall(f"Recipient '{recipient_id}' not found.".encode("utf-8"))
            print(f"User '{sender_id}' tried to send message to unknown recipient '{recipient_id}'.")

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

if __name__ == "__main__":
    tunnel = ngrok.connect(PORT, "tcp")
    public_url = tunnel.public_url  # e.g. 'tcp://0.tcp.ngrok.io:12345'

    # Parse host and port out of the public_url
    # public_url is something like 'tcp://0.tcp.ngrok.io:17890'
    parsed_url = public_url.replace("tcp://", "").split(":")
    ngrok_host = parsed_url[0]
    ngrok_port = parsed_url[1]

    print("==============================================")
    print(f"[NGROK] Public URL: {public_url}")
    print(f"[NGROK] Host: {ngrok_host}, Port: {ngrok_port}")
    print("==============================================\n")

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    with server:
        ip, port = server.server_address
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        print(f"Local server running on {ip}:{port}.")
        print("Press Ctrl+C to stop.\n")

        try:
            server_thread.join()  # Keep the main thread running
        except KeyboardInterrupt:
            print("\nShutting down the server...")
            server.shutdown()
            server.server_close()
