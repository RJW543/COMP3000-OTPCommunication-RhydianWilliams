import socket
import threading

CHUNK = 1024

# Global dictionaries protected by a lock
clients = {}        # { user_id: (socket, address) }
pending_calls = {}  # { callee_user_id: caller_user_id }
active_calls = {}   # { user_id: partner_user_id }
lock = threading.Lock()

def read_line(conn):
    """
    Read until newline from 'conn'; returns the decoded line (without newline).
    Returns an empty string if the connection is closed.
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
    Receive exactly 'n' bytes or return None if connection is closed prematurely.
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
    Per-client loop. Expects "REGISTER <user_id>" first.
    Then handles commands (CALL, ANSWER, DECLINE, VOICE, HANGUP).
    Forwards audio data to the correct partner.
    """
    print(f"[+] New connection from {addr}")

    user_id = None
    try:
        # First message must be: REGISTER <user_id>
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
            if not line:  # connection closed
                break

            parts = line.strip().split()
            if not parts:
                continue
            cmd = parts[0].upper()

            with lock:
                if cmd == "CALL":
                    # CALL <destination_user_id>
                    if len(parts) < 2:
                        continue
                    dest = parts[1]
                    if dest not in clients:
                        # Destination user is offline
                        conn.sendall(b"CALL_FAILED User not online\n")
                        print(f"[-] {user_id} tried calling offline user {dest}")
                    elif dest in active_calls or dest in pending_calls:
                        # Destination is busy
                        conn.sendall(b"CALL_FAILED User busy\n")
                        print(f"[-] {user_id} tried calling busy user {dest}")
                    elif user_id in active_calls or user_id in pending_calls.values():
                        # Caller is already in a call or pending
                        conn.sendall(b"CALL_FAILED You are already in a call\n")
                    else:
                        # Create a pending call: callee -> caller
                        pending_calls[dest] = user_id
                        callee_conn, _ = clients[dest]
                        try:
                            callee_conn.sendall(f"INCOMING_CALL {user_id}\n".encode())
                        except:
                            pass
                        print(f"[+] {user_id} calling {dest}")

                elif cmd == "ANSWER":
                    # ANSWER <caller_user_id>
                    if len(parts) < 2:
                        continue
                    caller = parts[1]
                    # Check if there's a pending call from <caller> to <user_id>
                    if user_id not in pending_calls or pending_calls[user_id] != caller:
                        print(f"[-] {user_id} answered but no pending call from {caller}")
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
                    # DECLINE <caller_user_id>
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
                    # Next CHUNK bytes are audio data to forward
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
                    if user_id in active_calls:
                        partner = active_calls[user_id]
                        partner_conn, _ = clients[partner]
                        try:
                            partner_conn.sendall(b"HANGUP\n")
                        except:
                            pass
                        # Remove from active_calls both ways
                        del active_calls[user_id]
                        if partner in active_calls:
                            del active_calls[partner]
                        print(f"[!] {user_id} hung up call with {partner}")

                else:
                    print(f"[-] Unknown command from {user_id}: {line}")

    except Exception as e:
        print(f"[!] Exception with client {addr}: {e}")

    finally:
        # Cleanup when a client disconnects
        with lock:
            # Remove from clients
            if user_id and user_id in clients:
                del clients[user_id]
            # Remove pending call if any
            if user_id in pending_calls:
                del pending_calls[user_id]
            # If user was in an active call, notify partner
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
    # The port we listen on 
    port = 5000

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind to all interfaces so it can accept external connections
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(5)

    print(f"[+] Server listening on 0.0.0.0:{port}")
    print("    (If behind a router/firewall, you must port-forward 5000 to this machine.)")

    while True:
        conn, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
