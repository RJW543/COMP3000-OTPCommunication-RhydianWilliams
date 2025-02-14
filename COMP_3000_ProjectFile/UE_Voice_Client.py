# client.py
import socket
import threading
import tkinter as tk
import queue
import pyaudio

# Audio stream configuration
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# Global flag to control audio threads
running = False

# Thread-safe log queue for GUI messages
log_queue = queue.Queue()

def log(message):
    """Add a log message to the queue."""
    log_queue.put(message)

def process_log_queue(text_widget):
    """Update the log text widget periodically with messages."""
    while not log_queue.empty():
        msg = log_queue.get()
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
    text_widget.after(100, process_log_queue, text_widget)

def recvall(sock, n):
    """
    Receive exactly n bytes from the socket.
    Returns the data or None if the connection is closed.
    """
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def send_audio(sock, dest_id, audio_stream):
    """Continuously capture audio and send it to the server with a header."""
    while running:
        try:
            data = audio_stream.read(CHUNK, exception_on_overflow=False)
            # Send header: "TO <destinationID>\n"
            header = f"TO {dest_id}\n".encode()
            sock.sendall(header)
            sock.sendall(data)
        except Exception as e:
            log(f"Error sending audio: {e}")
            break

def receive_audio(sock, audio_stream):
    """Continuously receive audio data from the server and play it."""
    while running:
        try:
            data = recvall(sock, CHUNK)
            if data is None:
                break
            audio_stream.write(data)
        except Exception as e:
            log(f"Error receiving audio: {e}")
            break

def start_voice_chat(server_host, server_port, user_id, dest_id):
    """Connect to the server, register, and start the send/receive threads."""
    global running
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_host, int(server_port)))
        # Send registration message: "REGISTER <userID>\n"
        sock.sendall(f"REGISTER {user_id}\n".encode())
        log("Connected and registered to server.")
    except Exception as e:
        log(f"Could not connect to server: {e}")
        return

    p = pyaudio.PyAudio()
    # Open an input stream for recording (microphone)
    input_stream = p.open(format=FORMAT,
                          channels=CHANNELS,
                          rate=RATE,
                          input=True,
                          frames_per_buffer=CHUNK)
    # Open an output stream for playback (speaker)
    output_stream = p.open(format=FORMAT,
                           channels=CHANNELS,
                           rate=RATE,
                           output=True,
                           frames_per_buffer=CHUNK)

    running = True
    # Start the thread to capture and send audio
    threading.Thread(target=send_audio, args=(sock, dest_id, input_stream), daemon=True).start()
    # Start the thread to receive and play audio
    threading.Thread(target=receive_audio, args=(sock, output_stream), daemon=True).start()

def stop_voice_chat():
    """Stop the audio threads."""
    global running
    running = False
    log("Voice chat stopped.")

def run_client_gui():
    """Run the Tkinter GUI for the client."""
    root = tk.Tk()
    root.title("Voice Chat Client")

    # Server Host entry 
    tk.Label(root, text="Server Host:").grid(row=0, column=0, sticky="e")
    server_host_entry = tk.Entry(root)
    server_host_entry.grid(row=0, column=1)
    server_host_entry.insert(0, "0.tcp.ngrok.io")  

    # Server Port entry 
    tk.Label(root, text="Server Port:").grid(row=1, column=0, sticky="e")
    server_port_entry = tk.Entry(root)
    server_port_entry.grid(row=1, column=1)
    server_port_entry.insert(0, "5000")  

    # User ID entry
    tk.Label(root, text="Your User ID:").grid(row=2, column=0, sticky="e")
    user_id_entry = tk.Entry(root)
    user_id_entry.grid(row=2, column=1)

    # Destination User ID entry
    tk.Label(root, text="Destination User ID:").grid(row=3, column=0, sticky="e")
    dest_id_entry = tk.Entry(root)
    dest_id_entry.grid(row=3, column=1)

    # Log display
    log_text = tk.Text(root, height=15, width=50)
    log_text.grid(row=4, column=0, columnspan=2)
    process_log_queue(log_text)

    def on_start():
        """Start voice chat using the provided parameters."""
        server_host = server_host_entry.get().strip()
        server_port = server_port_entry.get().strip()
        user_id = user_id_entry.get().strip()
        dest_id = dest_id_entry.get().strip()
        if not (server_host and server_port and user_id and dest_id):
            log("Please fill in all fields.")
            return
        threading.Thread(target=start_voice_chat,
                         args=(server_host, server_port, user_id, dest_id),
                         daemon=True).start()

    def on_stop():
        """Stop the voice chat."""
        stop_voice_chat()

    # Buttons to start and stop the voice chat
    start_button = tk.Button(root, text="Start Voice Chat", command=on_start)
    start_button.grid(row=5, column=0, pady=5)
    stop_button = tk.Button(root, text="Stop Voice Chat", command=on_stop)
    stop_button.grid(row=5, column=1, pady=5)

    root.mainloop()

if __name__ == "__main__":
    run_client_gui()
