import socket
import threading
from pyngrok import ngrok

CHUNK = 1024

# Global dictionaries protected by a lock
clients = {}        # { user_id: (socket, address) }
pending_calls = {}  # { callee_user_id: caller_user_id }
active_calls = {}   # { user_id: partner_user_id }
lock = threading.Lock()

def read_line(conn):
    """
    Read until a newline from conn; return the decoded line without the newline.
    If the connection closes, returns an empty string.
    """
    line = b""
    while True:
        chunk = conn.recv(1)
        if not chunk:
            return ""
        if chunk == b"\n":
            break
        line += chunk
    return line.decode("utf-8", errors="ignore")

def recvall(conn, n):
    """
    Receive exactly n bytes or return None if connection is closed prematurely.
    """
    data = b""
    while len(data) < n:
        part = conn.recv(n - len(data))
        if not part:
            return None
        data += part
    return data

def handle_client(conn, addr):
    """
    Main loop for each connected client.
    Expects a "REGISTER <user_id>" from the client, then handles calls and audio.
    """
    print(f"[+] New connection from {addr}")

    user_id = None
    try:
        # First message must be REGISTER <user_id>
        reg_line = read_line(conn)
        if not reg_line.startswith("REGISTER "):
            print(f"[-] Invalid registration from {addr}: {reg_line}")
            conn.close()
            return
        user_id = reg_line.split()[1]
        with lock:
            clients[user_id] = (conn, addr)
        print(f"[+] Registered user '{user_id}' from {addr}")

        while True:
            line = read_line(conn)
            if not line:
                # Connection closed
                break

            parts = line.strip().split()
            if not parts:
                continue
            cmd = parts[0].upper()

            with lock:
                if cmd == "CALL":
                    # CALL <destination_user>
                    if len(parts) < 2:
                        continue
                    destination = parts[1]
                    if destination not in clients:
                        # Destination user is offline
                        conn.sendall(b"CALL_FAILED User not online\n")
                        print(f"[-] {user_id} attempted call to offline user {destination}")
                    elif destination in active_calls or destination in pending_calls:
                        # Destination is busy
                        conn.sendall(b"CALL_FAILED User busy\n")
                        print(f"[-] {user_id} attempted call to busy user {destination}")
                    elif user_id in active_calls or user_id in pending_calls.values():
                        # Caller is already in a call or a pending call
                        conn.sendall(b"CALL_FAILED You are already in a call\n")
                    else:
                        # Mark a pending call: callee -> caller
                        pending_calls[destination] = user_id
                        callee_conn, _ = clients[destination]
                        try:
                            callee_conn.sendall(f"INCOMING_CALL {user_id}\n".encode())
                        except:
                            pass
                        print(f"[+] {user_id} calling {destination}")

                elif cmd == "ANSWER":
                    # ANSWER <caller_user>
                    if len(parts) < 2:
                        continue
                    caller = parts[1]
                    # Check if there's a pending call from <caller> to user_id
                    if user_id not in pending_calls or pending_calls[user_id] != caller:
                        print(f"[-] {user_id} tried to answer but no pending call from {caller}")
                        continue
                    # Move from pending_calls to active_calls
                    del pending_calls[user_id]
                    active_calls[user_id] = caller
                    active_calls[caller] = user_id
                    caller_conn, _ = clients[caller]
                    try:
                        caller_conn.sendall(f"CALL_ACCEPTED {user_id}\n".encode())
                    except:
                        pass
                    print(f"[+] {user_id} answered call from {caller}")

                elif cmd == "DECLINE":
                    # DECLINE <caller_user>
                    if len(parts) < 2:
                        continue
                    caller = parts[1]
                    if user_id in pending_calls and pending_calls[user_id] == caller:
                        del pending_calls[user_id]
                        caller_conn, _ = clients[caller]
                        try:
                            caller_conn.sendall(f"CALL_DECLINED {user_id}\n".encode())
                        except:
                            pass
                        print(f"[-] {user_id} declined call from {caller}")

                elif cmd == "VOICE":
                    # VOICE command means the next CHUNK bytes are audio data to forward
                    data = recvall(conn, CHUNK)
                    if data is None:
                        break
                    if user_id in active_calls:
                        partner = active_calls[user_id]
                        if partner in clients:
                            partner_conn, _ = clients[partner]
                            try:
                                partner_conn.sendall(b"VOICE\n")
                                partner_conn.sendall(data)
                            except:
                                pass

                elif cmd == "HANGUP":
                    # End an active call
                    if user_id in active_calls:
                        partner = active_calls[user_id]
                        partner_conn, _ = clients[partner]
                        try:
                            partner_conn.sendall(b"HANGUP\n")
                        except:
                            pass
                        # Remove both sides from active_calls
                        del active_calls[user_id]
                        if partner in active_calls:
                            del active_calls[partner]
                        print(f"[!] {user_id} hung up call with {partner}")

                else:
                    print(f"[-] Unknown command from {user_id}: {line}")

    except Exception as e:
        print(f"[!] Exception with client {addr}: {e}")

    finally:
        # Cleanup on client disconnect
        with lock:
            if user_id and user_id in clients:
                del clients[user_id]
            # If user was in a pending call, remove it
            if user_id in pending_calls:
                del pending_calls[user_id]
            # If user was in an active call, hang up with partner
            if user_id in active_calls:
                partner = active_calls[user_id]
                if partner in clients:
                    partner_conn, _ = clients[partner]
                    try:
                        partner_conn.sendall(b"HANGUP\n")
                    except:
                        pass
                del active_calls[user_id]
                if partner in active_calls:
                    del active_calls[partner]
        conn.close()
        print(f"[x] Client '{user_id}' disconnected")


def main():
    # Choose a local port to listen on 
    port = 5000

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(5)
    print(f"[+] Server listening on port {port}")

    # Create a TCP tunnel with Ngrok
    tunnel = ngrok.connect(port, "tcp")
    public_url = tunnel.public_url  # e.g. "tcp://0.tcp.ngrok.io:12345"
    print(f"[+] Ngrok tunnel: {public_url}")

    # Parse host/port from that URL
    stripped = public_url.replace("tcp://", "")  # "0.tcp.ngrok.io:12345"
    ngrok_host, ngrok_port = stripped.split(":")
    print("[+] Use this host/port in the client:")
    print(f"    Host = {ngrok_host}")
    print(f"    Port = {ngrok_port}")

    # Accept clients in a loop
    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
