# client.py
import socket
import threading
import tkinter as tk
from tkinter import ttk
import queue
import pyaudio
import time

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
    """Append message to GUI log."""
    log_queue.put(message)

def process_log_queue(text_widget):
    """Periodically update the log text widget."""
    while not log_queue.empty():
        msg = log_queue.get()
        text_widget.insert(tk.END, msg + "\n")
        text_widget.see(tk.END)
    text_widget.after(100, process_log_queue, text_widget)

def list_audio_devices():
    """
    Returns two lists:
      - input_devices: list of tuples (index, name) for devices with input channels.
      - output_devices: list of tuples (index, name) for devices with output channels.
    """
    pa = pyaudio.PyAudio()
    input_devices = []
    output_devices = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            input_devices.append((i, info.get("name", f"Device {i}")))
        if info.get("maxOutputChannels", 0) > 0:
            output_devices.append((i, info.get("name", f"Device {i}")))
    pa.terminate()
    return input_devices, output_devices

def read_line(s):
    """Read a line (until newline) from socket s."""
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
    """Receive exactly n bytes from socket s, or return None if connection closed."""
    data = b""
    while len(data) < n:
        packet = s.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def audio_send():
    """Continuously capture audio from the microphone and send to the server while in a call."""
    global in_call, sock, input_stream
    while in_call:
        try:
            data = input_stream.read(CHUNK, exception_on_overflow=False)
            if not data:
                continue
            sock.sendall("VOICE\n".encode())
            sock.sendall(data)
        except BrokenPipeError:
            log("Broken pipe error encountered. Ending call.")
            in_call = False
            break
        except Exception as e:
            log(f"Error sending audio: {e}")
            in_call = False
            break
        time.sleep(0.01)

def start_audio_send_thread():
    """Start the audio sending thread if not already running."""
    global audio_send_thread
    if audio_send_thread is None or not audio_send_thread.is_alive():
        audio_send_thread = threading.Thread(target=audio_send, daemon=True)
        audio_send_thread.start()

def listen_to_server():
    """Listen for messages (signaling and voice data) from the server."""
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
                    # Discard data if not in call.
                    _ = recvall(sock, CHUNK)
            else:
                log(f"Unknown command from server: {line}")
        except Exception as e:
            log(f"Error in listen thread: {e}")
            break

def connect_to_server(server_host, server_port, user_id, input_device_index, output_device_index):
    """
    Connect to the server, register, and initialise audio streams using the provided device indices.
    """
    global sock, p, input_stream, output_stream
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((server_host, int(server_port)))
        sock.sendall(f"REGISTER {user_id}\n".encode())
        log("Connected and registered to server.")
    except Exception as e:
        log(f"Could not connect to server: {e}")
        return False

    # Initialise PyAudio streams with the selected devices.
    try:
        p = pyaudio.PyAudio()
        input_stream = p.open(format=FORMAT,
                              channels=CHANNELS,
                              rate=RATE,
                              input=True,
                              input_device_index=input_device_index,
                              frames_per_buffer=CHUNK)
        output_stream = p.open(format=FORMAT,
                               channels=CHANNELS,
                               rate=RATE,
                               output=True,
                               output_device_index=output_device_index,
                               frames_per_buffer=CHUNK)
    except Exception as e:
        log(f"Error initialising audio: {e}")
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

# --- Testing Functions for Audio Devices ---

def test_output_device(device_index):
    """Generate and play a 1-second 440Hz tone on the selected output device."""
    try:
        import numpy as np
    except ImportError:
        log("NumPy is required for output testing. Please install it via pip.")
        return

    pa_test = pyaudio.PyAudio()
    duration = 1.0  # seconds
    fs = RATE
    f = 440.0  # tone frequency (A4)
    t = np.linspace(0, duration, int(fs * duration), False)
    tone = 0.5 * np.sin(2 * np.pi * f * t)
    # Convert to 16-bit PCM
    tone = (tone * 32767).astype(np.int16).tobytes()
    try:
        stream = pa_test.open(format=FORMAT,
                              channels=1,
                              rate=RATE,
                              output=True,
                              output_device_index=device_index)
        stream.write(tone)
        stream.stop_stream()
        stream.close()
        log("Test output: Tone played successfully.")
    except Exception as e:
        log(f"Test output error: {e}")
    pa_test.terminate()

def test_input_device(input_device_index, output_device_index):
    """Record 3 seconds from the selected input device and then play it back on the selected output device."""
    pa_test = pyaudio.PyAudio()
    record_seconds = 3
    frames = []
    try:
        stream_in = pa_test.open(format=FORMAT,
                                 channels=CHANNELS,
                                 rate=RATE,
                                 input=True,
                                 input_device_index=input_device_index,
                                 frames_per_buffer=CHUNK)
        log("Test input: Recording for 3 seconds. Please speak...")
        for i in range(0, int(RATE / CHUNK * record_seconds)):
            data = stream_in.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
        stream_in.stop_stream()
        stream_in.close()
        log("Test input: Recording complete. Playing back...")
        
        stream_out = pa_test.open(format=FORMAT,
                                  channels=CHANNELS,
                                  rate=RATE,
                                  output=True,
                                  output_device_index=output_device_index,
                                  frames_per_buffer=CHUNK)
        for frame in frames:
            stream_out.write(frame)
        stream_out.stop_stream()
        stream_out.close()
        log("Test input: Playback complete.")
    except Exception as e:
        log(f"Test input error: {e}")
    pa_test.terminate()

# --- GUI ---

def run_client_gui():
    """Run the Tkinter GUI for the client with device selection and test options."""
    root = tk.Tk()
    root.title("Voice Chat Client")

    # Get available audio devices.
    input_devs, output_devs = list_audio_devices()
    # Build option lists for display.
    input_options = [f"{i}: {name}" for (i, name) in input_devs]
    output_options = [f"{i}: {name}" for (i, name) in output_devs]
    # Create dictionaries to map the display string to the device index.
    input_device_dict = {f"{i}: {name}": i for (i, name) in input_devs}
    output_device_dict = {f"{i}: {name}": i for (i, name) in output_devs}

    # Connection frame.
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

    # Audio device selection.
    tk.Label(conn_frame, text="Input Device:").grid(row=3, column=0, sticky="e")
    selected_input_device = tk.StringVar(conn_frame)
    if input_options:
        selected_input_device.set(input_options[0])
    else:
        selected_input_device.set("No input devices")
    input_menu = ttk.OptionMenu(conn_frame, selected_input_device, selected_input_device.get(), *input_options)
    input_menu.grid(row=3, column=1)

    tk.Label(conn_frame, text="Output Device:").grid(row=4, column=0, sticky="e")
    selected_output_device = tk.StringVar(conn_frame)
    if output_options:
        selected_output_device.set(output_options[0])
    else:
        selected_output_device.set("No output devices")
    output_menu = ttk.OptionMenu(conn_frame, selected_output_device, selected_output_device.get(), *output_options)
    output_menu.grid(row=4, column=1)

    def on_connect():
        """Handle the Connect button click in a separate thread."""
        def connect_thread():
            server_host = server_host_entry.get().strip()
            server_port = server_port_entry.get().strip()
            user_id = user_id_entry.get().strip()
            input_sel = selected_input_device.get()
            output_sel = selected_output_device.get()
            if not (server_host and server_port and user_id and input_sel and output_sel):
                log("Please fill in all fields and select devices.")
                return
            input_device_index = input_device_dict.get(input_sel)
            output_device_index = output_device_dict.get(output_sel)
            if connect_to_server(server_host, server_port, user_id, input_device_index, output_device_index):
                log("Connection established.")
            else:
                log("Connection failed.")
        threading.Thread(target=connect_thread, daemon=True).start()

    connect_button = tk.Button(conn_frame, text="Connect", width=12, command=on_connect)
    connect_button.grid(row=5, column=0, columnspan=2, pady=5)

    # Device testing buttons.
    def on_test_output():
        output_sel = selected_output_device.get()
        if output_sel not in output_device_dict:
            log("Invalid output device selection.")
            return
        device_index = output_device_dict[output_sel]
        test_output_device(device_index)

    def on_test_input():
        input_sel = selected_input_device.get()
        output_sel = selected_output_device.get()
        if input_sel not in input_device_dict or output_sel not in output_device_dict:
            log("Invalid device selection for test input.")
            return
        input_index = input_device_dict[input_sel]
        output_index = output_device_dict[output_sel]
        # Run test_input_device in a separate thread to avoid blocking the GUI.
        threading.Thread(target=test_input_device, args=(input_index, output_index), daemon=True).start()

    test_frame = tk.Frame(conn_frame)
    test_frame.grid(row=6, column=0, columnspan=2, pady=5)
    test_output_button = tk.Button(test_frame, text="Test Output", command=on_test_output)
    test_output_button.pack(side=tk.LEFT, padx=5)
    test_input_button = tk.Button(test_frame, text="Test Input", command=on_test_input)
    test_input_button.pack(side=tk.LEFT, padx=5)

    # Call controls frame.
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

    # Log display.
    log_text = tk.Text(root, height=15, width=60)
    log_text.pack(pady=5)
    process_log_queue(log_text)

    root.mainloop()

if __name__ == "__main__":
    run_client_gui()
