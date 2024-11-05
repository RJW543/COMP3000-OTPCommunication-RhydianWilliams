import socket
import threading

HOST = '0.0.0.0'  # Listen on all interfaces
PORT = 65432
clients = {}  # Stores client_socket against userID


def handle_client(client_socket, user_id):
    """Handles messages from a connected client."""
    while True:
        try:
            # Receive and decode the message
            message = client_socket.recv(1024).decode("utf-8")
            if message:
                recipient_id, encrypted_message = message.split("|", 1)
                print(f"Received message for {recipient_id} from {user_id}: {encrypted_message}")
                send_message_to_recipient(recipient_id, encrypted_message, user_id)
        except:
            print(f"Connection lost for user {user_id}.")
            clients.pop(user_id)
            client_socket.close()
            break


def send_message_to_recipient(recipient_id, message, sender_id):
    """Send a message to a specific recipient by userID."""
    recipient_socket = clients.get(recipient_id)
    if recipient_socket:
        try:
            full_message = f"{sender_id}|{message}"
            recipient_socket.send(full_message.encode("utf-8"))
        except:
            print(f"Failed to send message to {recipient_id}. Removing client.")
            clients.pop(recipient_id)
            recipient_socket.close()


def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"Server running on {HOST}:{PORT}...")

    while True:
        client_socket, addr = server.accept()
        print(f"New connection from {addr}")

        # Assign a userID to the new client
        user_id = client_socket.recv(1024).decode("utf-8")
        if user_id in clients:
            client_socket.send("UserID already taken. Connection closed.".encode("utf-8"))
            client_socket.close()
            continue

        clients[user_id] = client_socket
        client_socket.send("Connected successfully.".encode("utf-8"))
        print(f"User {user_id} connected.")

        client_thread = threading.Thread(target=handle_client, args=(client_socket, user_id))
        client_thread.start()


if __name__ == "__main__":
    start_server()
