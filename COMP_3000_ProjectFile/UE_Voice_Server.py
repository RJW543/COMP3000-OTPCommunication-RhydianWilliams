# server.py
import socket
import threading
import tkinter as tk
import queue
from pyngrok import ngrok

# Audio packet size
CHUNK_SIZE = 1024

# Global dictionaries (protected by clients_lock)
clients = {}       # { user_id: socket }
pending_calls = {} # { callee_user_id: caller_user_id }
active_calls = {}  # { user_id: peer_user_id }
clients_lock = threading.Lock()

# Queue for log messages to the GUI
log_queue = queue.Queue()

def log(message):
    log_queue.put(message)

def process_log_queue(text_widget):
    while not log_queue.empty():
        msg = log_queue.get()
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
    text_widget.after(100, process_log_queue, text_widget)

def read_line(conn):
    """Read from the socket until a newline; return the decoded string (without newline)."""
    line = b""
    while True:
        ch = conn.recv(1)
        if not ch:
            break
        if ch == b'\n':
            break
        line += ch
    return line.decode('utf-8')

def recvall(conn, n):
    """Read exactly n bytes from conn (or return None if connection is closed)."""
    data = b""
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def handle_client(conn, addr):
    log(f"New connection from {addr}")
    user_id = None
    try:
        # Expect registration: "REGISTER <userID>\n"
        reg_line = read_line(conn)
        if not reg_line.startswith("REGISTER "):
            log(f"Invalid registration from {addr}: {reg_line}")
            conn.close()
            return
        user_id = reg_line.split()[1].strip()
        with clients_lock:
            clients[user_id] = conn
        log(f"Client registered: {user_id} from {addr}")

        while True:
            # Read a command line from the client.
            command_line = read_line(conn)
            if not command_line:
                break  # connection closed

            tokens = command_line.strip().split()
            if not tokens:
                continue
            cmd = tokens[0].upper()

            with clients_lock:
                if cmd == "CALL":
                    # Caller: "CALL <destination>"
                    if len(tokens) < 2:
                        continue
                    dest = tokens[1].strip()
                    if dest not in clients:
                        conn.sendall("CALL_FAILED User not online\n".encode())
                        log(f"{user_id} attempted call to offline user {dest}")
                    elif dest in active_calls or dest in pending_calls:
                        conn.sendall("CALL_FAILED User busy\n".encode())
                        log(f"{user_id} attempted call to busy user {dest}")
                    elif user_id in active_calls or user_id in pending_calls.values():
                        conn.sendall("CALL_FAILED You are already in a call or call pending\n".encode())
                        log(f"{user_id} attempted call while already busy")
                    else:
                        # Store pending call: key = callee, value = caller.
                        pending_calls[dest] = user_id
                        # Notify destination
                        try:
                            clients[dest].sendall(f"INCOMING_CALL {user_id}\n".encode())
                            log(f"Call from {user_id} to {dest} forwarded.")
                        except Exception as e:
                            log(f"Error notifying {dest}: {e}")
                elif cmd == "ANSWER":
                    # Callee answering: "ANSWER <caller>"
                    if len(tokens) < 2:
                        continue
                    caller = tokens[1].strip()
                    if user_id not in pending_calls or pending_calls.get(user_id) != caller:
                        log(f"{user_id} sent ANSWER but no pending call from {caller}")
                        continue
                    # Remove from pending and mark active call (bidirectionally)
                    del pending_calls[user_id]
                    active_calls[user_id] = caller
                    active_calls[caller] = user_id
                    try:
                        clients[caller].sendall(f"CALL_ACCEPTED {user_id}\n".encode())
                        log(f"{user_id} answered call from {caller}. Call active.")
                    except Exception as e:
                        log(f"Error notifying {caller} of call acceptance: {e}")
                elif cmd == "DECLINE":
                    # Callee declining: "DECLINE <caller>"
                    if len(tokens) < 2:
                        continue
                    caller = tokens[1].strip()
                    if user_id in pending_calls and pending_calls.get(user_id) == caller:
                        del pending_calls[user_id]
                        try:
                            clients[caller].sendall(f"CALL_DECLINED {user_id}\n".encode())
                            log(f"{user_id} declined call from {caller}.")
                        except Exception as e:
                            log(f"Error notifying {caller} of call decline: {e}")
                elif cmd == "VOICE":
                    # Voice data follows this header.
                    data = recvall(conn, CHUNK_SIZE)
                    if data is None:
                        break
                    # Forward to the call partner if in active call.
                    if user_id in active_calls:
                        partner = active_calls[user_id]
                        if partner in clients:
                            try:
                                clients[partner].sendall("VOICE\n".encode())
                                clients[partner].sendall(data)
                            except Exception as e:
                                log(f"Error forwarding voice from {user_id} to {partner}: {e}")
                elif cmd == "HANGUP":
                    # End the active call.
                    if user_id in active_calls:
                        partner = active_calls[user_id]
                        try:
                            if partner in clients:
                                clients[partner].sendall("HANGUP\n".encode())
                        except Exception as e:
                            log(f"Error sending HANGUP to {partner}: {e}")
                        # Remove both from active_calls.
                        del active_calls[user_id]
                        if partner in active_calls:
                            del active_calls[partner]
                        log(f"{user_id} hung up the call with {partner}")
                else:
                    log(f"Unknown command from {user_id}: {command_line}")
    except Exception as e:
        log(f"Exception with client {addr}: {e}")
    finally:
        with clients_lock:
            if user_id:
                # Clean up pending call if any.
                if user_id in pending_calls:
                    del pending_calls[user_id]
                # If in an active call, notify the partner.
                if user_id in active_calls:
                    partner = active_calls[user_id]
                    try:
                        if partner in clients:
                            clients[partner].sendall("HANGUP\n".encode())
                    except Exception as e:
                        log(f"Error notifying {partner} on disconnect: {e}")
                    if partner in active_calls:
                        del active_calls[partner]
                    del active_calls[user_id]
                # Remove from clients.
                if user_id in clients:
                    del clients[user_id]
                log(f"Client {user_id} disconnected")
        conn.close()

def start_server(port, text_widget):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("", port))
    server_socket.listen(5)
    log(f"Server listening on port {port}")

    # Open an Ngrok tunnel for TCP.
    public_url = ngrok.connect(port, "tcp")
    log(f"Ngrok tunnel established: {public_url}")
    text_widget.master.title(f"Server - {public_url}")

    while True:
        try:
            conn, addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            log(f"Server error: {e}")
            break

def run_server_gui():
    root = tk.Tk()
    root.title("Voice Chat Server")
    text = tk.Text(root, height=20, width=60)
    text.pack()
    process_log_queue(text)
    
    port = 5000  
    threading.Thread(target=start_server, args=(port, text), daemon=True).start()
    root.mainloop()

if __name__ == "__main__":
    run_server_gui()
