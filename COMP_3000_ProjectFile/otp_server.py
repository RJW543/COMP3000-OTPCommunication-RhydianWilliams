import socket
import threading

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 65432
clients = []

def handle_client(client_socket):
    """Handles messages from a connected client."""
    while True:
        try:
            # Receive and decode the message
            message = client_socket.recv(1024).decode("utf-8")
            if message:
                print(f"Broadcasting message: {message}")
                broadcast_message(message, client_socket)
        except:
            print("Connection lost.")
            clients.remove(client_socket)
            client_socket.close()
            break

def broadcast_message(message, sender_socket):
    for client in clients:
        if client != sender_socket:
            try:
                client.send(message.encode("utf-8"))
            except:
                clients.remove(client)
                client.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"Server running on {HOST}:{PORT}...")

    while True:
        client_socket, addr = server.accept()
        print(f"New connection from {addr}")
        clients.append(client_socket)
        client_thread = threading.Thread(target=handle_client, args=(client_socket,))
        client_thread.start()

if __name__ == "__main__":
    start_server()
