# client.py
import socket
import threading
import tkinter as tk
import queue
import pyaudio

# Audio configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# Global variables for connection and call state.
sock = None
in_call = False
call_partner = None
pending_call = None  # Holds the caller ID when an incoming call arrives.
audio_send_thread = None

# PyAudio instance and streams (initialised after connecting)
p = None
input_stream = None
output_stream = None

# Thread-safe log queue for GUI messages.
log_queue = queue.Queue()

def log(message):
    log_queue.put(message)

def process_log_queue(text_widget):
    while not log_queue.empty():
        msg = log_queue.get()
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
    text_widget.after(100, process_log_queue, text_widget)

def read_line(s):
    """Read from socket s until a newline character; return decoded string (without newline)."""
    line = b""
    while True:
        ch = s.recv(1)
        if not ch:
            break
        if ch == b'\n':
            break
        line += ch
    return line.decode('utf-8')

def recvall(s, n):
    """Receive exactly n bytes from socket s (or return None if connection is closed)."""
    data = b""
    while len(data) < n:
        packet = s.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def audio_send():
    """Continuously capture audio and send to the server while in a call."""
    global in_call, sock, input_stream
    while in_call:
        try:
            data = input_stream.read(CHUNK, exception_on_overflow=False)
            sock.sendall("VOICE\n".encode())
            sock.sendall(data)
        except Exception as e:
            log(f"Error sending audio: {e}")
            break

def start_audio_send_thread():
    global audio_send_thread
    if audio_send_thread is None or not audio_send_thread.is_alive():
        audio_send_thread = threading.Thread(target=audio_send, daemon=True)
        audio_send_thread.start()

def listen_to_server():
    """Listen on the socket for signaling and voice data from the server."""
    global in_call, call_partner, pending_call, sock, output_stream
    while True:
        try:
            line = read_line(sock)
            if not line:
                log("Disconnected from server.")
                break
            parts = line.strip().split()
            if not parts:
                continue
            cmd = parts[0].upper()

            if cmd == "INCOMING_CALL":
                # Server notifies: "INCOMING_CALL <caller>"
                pending_call = parts[1] if len(parts) > 1 else "Unknown"
                log(f"Incoming call from {pending_call}. Click 'Answer' or 'Decline'.")
            elif cmd == "CALL_ACCEPTED":
                # Caller is notified: "CALL_ACCEPTED <callee>"
                call_partner = parts[1] if len(parts) > 1 else "Unknown"
                in_call = True
                log(f"Call accepted by {call_partner}. You are now in a call.")
                start_audio_send_thread()
            elif cmd == "CALL_DECLINED":
                call_partner = parts[1] if len(parts) > 1 else "Unknown"
                log(f"Call declined by {call_partner}.")
            elif cmd == "CALL_FAILED":
                reason = " ".join(parts[1:]) if len(parts) > 1 else "Unknown reason"
                log(f"Call failed: {reason}")
            elif cmd == "HANGUP":
                log("Call ended by partner.")
                in_call = False
                call_partner = None
            elif cmd == "VOICE":
                # Voice packet is incoming.
                if in_call:
                    data = recvall(sock, CHUNK)
                    if data:
                        output_stream.write(data)
                else:
                    # If not in call, discard or ignore.
                    _ = recvall(sock, CHUNK)
            else:
                log(f"Unknown command from server: {line}")
        except Exception as e:
            log(f"Error in listen thread: {e}")
            break

def connect_to_server(server_host, server_port, user_id):
    """Connect to the server, send registration, and initialize audio streams."""
    global sock, p, input_stream, output_stream
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_host, int(server_port)))
        sock.sendall(f"REGISTER {user_id}\n".encode())
        log("Connected and registered to server.")
    except Exception as e:
        log(f"Could not connect to server: {e}")
        return False

    # Initialise PyAudio streams.
    try:
        p = pyaudio.PyAudio()
        input_stream = p.open(format=FORMAT,
                              channels=CHANNELS,
                              rate=RATE,
                              input=True,
                              frames_per_buffer=CHUNK)
        output_stream = p.open(format=FORMAT,
                               channels=CHANNELS,
                               rate=RATE,
                               output=True,
                               frames_per_buffer=CHUNK)
    except Exception as e:
        log(f"Error initializing audio: {e}")
        return False

    # Start a thread to listen to server messages.
    threading.Thread(target=listen_to_server, daemon=True).start()
    return True

def call_user(dest):
    """Send a call request to the destination user."""
    if sock:
        try:
            sock.sendall(f"CALL {dest}\n".encode())
            log(f"Calling {dest} ...")
        except Exception as e:
            log(f"Error sending CALL: {e}")
    else:
        log("Not connected to server.")

def answer_call():
    """Answer an incoming call."""
    global pending_call, in_call, call_partner
    if pending_call:
        try:
            sock.sendall(f"ANSWER {pending_call}\n".encode())
            in_call = True
            call_partner = pending_call
            log(f"Answered call from {pending_call}.")
            start_audio_send_thread()
            pending_call = None
        except Exception as e:
            log(f"Error sending ANSWER: {e}")
    else:
        log("No incoming call to answer.")

def decline_call():
    """Decline an incoming call."""
    global pending_call
    if pending_call:
        try:
            sock.sendall(f"DECLINE {pending_call}\n".encode())
            log(f"Declined call from {pending_call}.")
            pending_call = None
        except Exception as e:
            log(f"Error sending DECLINE: {e}")
    else:
        log("No incoming call to decline.")

def hangup_call():
    """Hang up the current call."""
    global in_call, call_partner
    if in_call:
        try:
            sock.sendall("HANGUP\n".encode())
            log("Call hung up.")
        except Exception as e:
            log(f"Error sending HANGUP: {e}")
        in_call = False
        call_partner = None
    else:
        log("Not in a call.")

def run_client_gui():
    """Run the Tkinter GUI for the client."""
    root = tk.Tk()
    root.title("Voice Chat Client")

    # Connection frame
    conn_frame = tk.Frame(root)
    conn_frame.pack(pady=5)
    tk.Label(conn_frame, text="Server Host:").grid(row=0, column=0, sticky="e")
    server_host_entry = tk.Entry(conn_frame)
    server_host_entry.grid(row=0, column=1)
    server_host_entry.insert(0, "0.tcp.ngrok.io") 

    tk.Label(conn_frame, text="Server Port:").grid(row=1, column=0, sticky="e")
    server_port_entry = tk.Entry(conn_frame)
    server_port_entry.grid(row=1, column=1)
    server_port_entry.insert(0, "5000")  

    tk.Label(conn_frame, text="Your User ID:").grid(row=2, column=0, sticky="e")
    user_id_entry = tk.Entry(conn_frame)
    user_id_entry.grid(row=2, column=1)

    connect_button = tk.Button(conn_frame, text="Connect", width=12, 
                               command=lambda: connect_to_server(
                                   server_host_entry.get().strip(),
                                   server_port_entry.get().strip(),
                                   user_id_entry.get().strip()
                               ))
    connect_button.grid(row=3, column=0, columnspan=2, pady=5)

    # Call controls frame
    call_frame = tk.Frame(root)
    call_frame.pack(pady=5)
    tk.Label(call_frame, text="Call User (for outgoing calls):").grid(row=0, column=0, sticky="e")
    call_dest_entry = tk.Entry(call_frame)
    call_dest_entry.grid(row=0, column=1)

    call_button = tk.Button(call_frame, text="Call", width=12,
                            command=lambda: call_user(call_dest_entry.get().strip()))
    call_button.grid(row=1, column=0, pady=5)

    answer_button = tk.Button(call_frame, text="Answer", width=12, command=answer_call)
    answer_button.grid(row=1, column=1, pady=5)

    decline_button = tk.Button(call_frame, text="Decline", width=12, command=decline_call)
    decline_button.grid(row=2, column=0, pady=5)

    hangup_button = tk.Button(call_frame, text="Hang Up", width=12, command=hangup_call)
    hangup_button.grid(row=2, column=1, pady=5)

    # Log display
    log_text = tk.Text(root, height=15, width=60)
    log_text.pack(pady=5)
    process_log_queue(log_text)

    root.mainloop()

if __name__ == "__main__":
    run_client_gui()
