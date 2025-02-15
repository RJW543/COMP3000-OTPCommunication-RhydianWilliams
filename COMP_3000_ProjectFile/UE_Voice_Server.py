import socket
import threading

# Forwarding server that relays audio data between two clients

HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 50007      # Arbitrary choice for the forwarding server port

clients = {}

calls_in_progress = {}

def handle_client(conn, addr):
    """
    Handles client communication with the server.
    Each client:
      - Sends its user_id upon connection
      - Waits for instructions (call requests, etc.)
      - Sends audio if in a call
    """
    global clients, calls_in_progress
    
    try:
        # First message from client should be the user_id
        user_id = conn.recv(1024).decode('utf-8')
        if not user_id:
            return
        print(f"[SERVER] New connection from {addr}, user_id={user_id}")
        
        # Store this client
        clients[user_id] = (conn, addr)

        while True:
            data = conn.recv(4096)
            if not data:
                break

            try:
                message = data.decode('utf-8', errors='ignore')
                if message.startswith("CALL|"):
                    parts = message.split("|")
                    if len(parts) == 2:
                        target_id = parts[1]
                        print(f"[SERVER] {user_id} wants to call {target_id}")

                        # Inform the target about an incoming call
                        if target_id in clients:
                            target_conn, _ = clients[target_id]
                            target_conn.sendall(f"INCOMING_CALL|{user_id}".encode('utf-8'))
                        else:
                            # If target is not online, send error back
                            conn.sendall(f"ERROR|User {target_id} not found".encode('utf-8'))

                elif message.startswith("ACCEPT|"):
                    parts = message.split("|")
                    if len(parts) == 2:
                        caller_id = parts[1]
                        print(f"[SERVER] {user_id} accepted call from {caller_id}")
                        # Mark call in progress
                        calls_in_progress[caller_id] = user_id
                        calls_in_progress[user_id] = caller_id
                        # Notify the caller that call is accepted
                        if caller_id in clients:
                            caller_conn, _ = clients[caller_id]
                            caller_conn.sendall(f"CALL_ACCEPTED|{user_id}".encode('utf-8'))

                elif message.startswith("AUDIO|"):
                    # Actual audio data forwarding
                    # The format is "AUDIO|<raw data>"
                    header, raw_audio = data.split(b'|', 1)
                    # Determine who we should forward to
                    if user_id in calls_in_progress:
                        target_id = calls_in_progress[user_id]
                        if target_id in clients:
                            target_conn, _ = clients[target_id]
                            # Prepend "AUDIO|" again for the recipient
                            target_conn.sendall(b"AUDIO|" + raw_audio)
                else:
                    pass
            except:
                if user_id in calls_in_progress:
                    target_id = calls_in_progress[user_id]
                    if target_id in clients:
                        target_conn, _ = clients[target_id]
                        # Prepend "AUDIO|" for the recipient
                        target_conn.sendall(b"AUDIO|" + data)

    except Exception as e:
        print(f"[SERVER] Exception: {e}")

    finally:
        print(f"[SERVER] Connection closed: {addr} user_id={user_id}")
        conn.close()
        if user_id in clients:
            del clients[user_id]
        # Remove from calls_in_progress
        remove_list = []
        for k, v in calls_in_progress.items():
            if k == user_id or v == user_id:
                remove_list.append(k)
        for key in remove_list:
            del calls_in_progress[key]

def start_server():
    print(f"[SERVER] Starting server on {HOST}:{PORT}")
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((HOST, PORT))
    server_socket.listen(5)
    print(f"[SERVER] Server listening...")

    while True:
        conn, addr = server_socket.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
        client_thread.start()

if __name__ == "__main__":
    start_server()
