import socket
import threading
import pyaudio
import time

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100

# Global flags/states
running = True
in_call = False
call_partner = None
pending_caller = None  # Set when we get "INCOMING_CALL <caller>"

# PyAudio streams
p = pyaudio.PyAudio()
input_stream = None
output_stream = None

def read_line(sock):
    """
    Read from 'sock' until newline; returns the string (without newline).
    Returns '' if connection closed.
    """
    line = b""
    while True:
        chunk = sock.recv(1)
        if not chunk:
            return ""
        if chunk == b"\n":
            break
        line += chunk
    return line.decode("utf-8", errors="ignore")

def recvall(sock, n):
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def listen_thread(sock):
    """
    Listen for commands/messages from the server:
    - INCOMING_CALL <caller>
    - CALL_ACCEPTED <callee>
    - CALL_DECLINED <callee>
    - CALL_FAILED <reason...>
    - HANGUP
    - VOICE
    """
    global in_call, call_partner, pending_caller, running

    while running:
        line = read_line(sock)
        if not line:
            print("[!] Disconnected from server.")
            break

        parts = line.strip().split()
        if not parts:
            continue
        cmd = parts[0].upper()

        if cmd == "INCOMING_CALL":
            if len(parts) >= 2:
                caller = parts[1]
                pending_caller = caller
                print(f"[!] Incoming call from '{caller}'. Type 'answer' or 'decline'.")
        elif cmd == "CALL_ACCEPTED":
            if len(parts) >= 2:
                callee = parts[1]
                in_call = True
                call_partner = callee
                print(f"[+] Call accepted. You are now in a call with '{callee}'.")
        elif cmd == "CALL_DECLINED":
            if len(parts) >= 2:
                callee = parts[1]
                print(f"[-] Your call was declined by '{callee}'.")
        elif cmd == "CALL_FAILED":
            reason = " ".join(parts[1:]) if len(parts) > 1 else "Unknown reason"
            print(f"[-] Call failed: {reason}")
        elif cmd == "HANGUP":
            print("[!] Call ended by other party.")
            in_call = False
            call_partner = None
        elif cmd == "VOICE":
            # Next CHUNK bytes are audio data
            data = recvall(sock, CHUNK)
            if data and in_call:
                output_stream.write(data)
        else:
            print(f"[?] Unknown server message: {line}")

def audio_send_thread(sock):
    """
    Continuously capture audio from the mic and send it to the server whenever we're in a call.
    """
    global in_call, running

    while running:
        if in_call:
            try:
                data = input_stream.read(CHUNK, exception_on_overflow=False)
                sock.sendall(b"VOICE\n")
                sock.sendall(data)
            except Exception as e:
                print(f"[!] Error sending audio: {e}")
                in_call = False
        else:
            time.sleep(0.1)

def main():
    global running, in_call, call_partner, pending_caller
    global input_stream, output_stream

    # Prompt user for server connection info
    host = input("Server host/IP (e.g. 192.168.1.10 or your VPS IP): ").strip()
    port = int(input("Server port (default 5000): ").strip())
    user_id = input("Your user ID (e.g. alice): ").strip()

    # Connect to server
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    print("[+] Connected to server.")
    sock.sendall(f"REGISTER {user_id}\n".encode())

    # Initialise PyAudio
    pa = pyaudio.PyAudio()
    input_stream = pa.open(format=FORMAT,
                           channels=CHANNELS,
                           rate=RATE,
                           input=True,
                           frames_per_buffer=CHUNK)
    output_stream = pa.open(format=FORMAT,
                            channels=CHANNELS,
                            rate=RATE,
                            output=True,
                            frames_per_buffer=CHUNK)

    # Start threads
    threading.Thread(target=listen_thread, args=(sock,), daemon=True).start()
    threading.Thread(target=audio_send_thread, args=(sock,), daemon=True).start()

    # Simple command loop
    print("\nCommands:")
    print("  call <user>   - Call another user")
    print("  answer        - Answer incoming call")
    print("  decline       - Decline incoming call")
    print("  hangup        - Hang up current call")
    print("  exit          - Quit client\n")

    while True:
        cmd = input("> ").strip().lower()
        if cmd.startswith("call "):
            _, dest_user = cmd.split(" ", 1)
            sock.sendall(f"CALL {dest_user}\n".encode())
        elif cmd == "answer":
            if pending_caller:
                sock.sendall(f"ANSWER {pending_caller}\n".encode())
                pending_caller = None
            else:
                print("No incoming call to answer.")
        elif cmd == "decline":
            if pending_caller:
                sock.sendall(f"DECLINE {pending_caller}\n".encode())
                pending_caller = None
            else:
                print("No incoming call to decline.")
        elif cmd == "hangup":
            if in_call:
                sock.sendall(b"HANGUP\n")
                in_call = False
                call_partner = None
            else:
                print("Not in a call.")
        elif cmd == "exit":
            print("[+] Exiting...")
            running = False
            sock.close()
            break
        else:
            print("Unknown command. Try: call <user>, answer, decline, hangup, exit")

    # Cleanup PyAudio
    input_stream.close()
    output_stream.close()
    pa.terminate()

if __name__ == "__main__":
    main()
