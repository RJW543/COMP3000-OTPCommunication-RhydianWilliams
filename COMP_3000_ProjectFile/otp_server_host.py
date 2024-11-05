# File: otp_server_host.py
import socket
import threading
import socketserver

HOST = '0.0.0.0'  # Listen on all interfaces, including internet
PORT = 65432
clients = {}  # Stores client_socket against userID

# Define a thread to handle each client
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

# Define function to send messages to a specific recipient
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

# Threaded server class
class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass

if __name__ == "__main__":
    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    print(f"Server running on {HOST}:{PORT} and accessible via the internet...")

    # Keep the main thread running
    try:
        server_thread.join()
    except KeyboardInterrupt:
        print("Shutting down the server...")
        server.shutdown()
        server.server_close()
