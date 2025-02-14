# server.py
import socket
import threading
import tkinter as tk
import queue
from pyngrok import ngrok

# Set the fixed size for each audio packet (in bytes)
CHUNK_SIZE = 1024

# Dictionary to hold connected clients: { userID: socket }
clients = {}
clients_lock = threading.Lock()

# A thread‐safe queue to send log messages to the GUI
log_queue = queue.Queue()

def log(message):
    """Add a log message to the queue."""
    log_queue.put(message)

def process_log_queue(text_widget):
    """Periodically check the log queue and update the text widget."""
    while not log_queue.empty():
        msg = log_queue.get()
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
    text_widget.after(100, process_log_queue, text_widget)

def read_line(conn):
    """
    Read from the socket until a newline character is encountered.
    Returns the decoded string (without the newline).
    """
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
    """
    Read exactly n bytes from the socket.
    Returns the data or None if the connection is closed.
    """
    data = b""
    while len(data) < n:
        packet = conn.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def handle_client(conn, addr):
    """Handle communication with a connected client."""
    log(f"New connection from {addr}")
    try:
        # The first message must be a registration command: "REGISTER <userID>\n"
        reg_msg = read_line(conn)
        if not reg_msg.startswith("REGISTER "):
            log(f"Invalid registration from {addr}: {reg_msg}")
            conn.close()
            return
        user_id = reg_msg.split()[1].strip()
        with clients_lock:
            clients[user_id] = conn
        log(f"Client registered: {user_id} from {addr}")

        # Loop to handle incoming voice data commands
        while True:
            header = read_line(conn)
            if not header:
                break  # connection closed
            if header.startswith("TO "):
                dest_id = header.split()[1].strip()
                # Read the next CHUNK_SIZE bytes as one audio packet
                audio_data = recvall(conn, CHUNK_SIZE)
                if audio_data is None:
                    break
                with clients_lock:
                    dest_conn = clients.get(dest_id)
                if dest_conn:
                    try:
                        dest_conn.sendall(audio_data)
                    except Exception as e:
                        log(f"Error sending to {dest_id}: {e}")
                else:
                    log(f"Destination {dest_id} not connected")
            else:
                log(f"Unknown command from {user_id}: {header}")
    except Exception as e:
        log(f"Exception with client {addr}: {e}")
    finally:
        with clients_lock:
            for uid, sock in list(clients.items()):
                if sock == conn:
                    del clients[uid]
                    log(f"Client {uid} disconnected")
        conn.close()

def start_server(port, text_widget):
    """Start the server socket, bind to the port, and open an Ngrok tunnel."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("", port))
    server_socket.listen(5)
    log(f"Server listening on port {port}")

    # Setup Ngrok tunnel for TCP
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
    """Start the Tkinter GUI for the server."""
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
