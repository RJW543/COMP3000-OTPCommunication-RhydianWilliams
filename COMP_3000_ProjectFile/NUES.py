import socket
import re
import subprocess
import threading
import sys

def run_loclx(local_port):
    """
    Run `loclx tunnel udp --port <local_port>` in the background.
    Parse its output to display the forwarding info.
    Returns the subprocess.Popen object for loclx and the
    discovered domain:port (if found).
    """
    cmd = ["loclx", "tunnel", "udp", "--port", str(local_port)]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    domain_port = None
    
    while True:
        line = process.stdout.readline()
        if not line:
            break  

        print("loclx:", line.strip())  

        if "Forwarding from " in line:
            match = re.search(r"Forwarding from udp://([^:]+):(\d+)", line)
            if match:
                domain = match.group(1)
                fwd_port = match.group(2)
                domain_port = f"{domain}:{fwd_port}"
                print(f"[SERVER] loclx tunnel active at {domain_port}")
                break

    return process, domain_port

class UdpForwarder:
    """
    A simple class that listens on a UDP port and forwards packets
    between exactly two clients.
    """
    def __init__(self, local_port):
        self.local_port = local_port
        self.sock = None

        self.client_addresses = set() 

        self.running = False
        self.forward_thread = None

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(('', self.local_port))
        self.running = True

        self.forward_thread = threading.Thread(target=self.forward_loop)
        self.forward_thread.start()

        print(f"[SERVER] Forwarder listening on UDP port {self.local_port}.")

    def forward_loop(self):
        """
        Loop that receives UDP data and forwards it to the *other* client.
        """
        while self.running:
            try:
                data, addr = self.sock.recvfrom(65535)  
            except OSError:
                break

            if addr not in self.client_addresses:
                self.client_addresses.add(addr)
                print(f"[SERVER] New client: {addr}")

            if len(self.client_addresses) == 2:
                for c in self.client_addresses:
                    if c != addr:
                        self.sock.sendto(data, c)

    def stop(self):
        self.running = False
        if self.sock:
            self.sock.close()
        if self.forward_thread and self.forward_thread.is_alive():
            self.forward_thread.join()

def main():
    local_port = 5100
    if len(sys.argv) > 1:
        local_port = int(sys.argv[1])

    print(f"[SERVER] Starting loclx on UDP port {local_port}...")
    loclx_process, domain_port = run_loclx(local_port)

    if not domain_port:
        print("[SERVER] Failed to parse loclx forwarding info. Exiting.")
        if loclx_process:
            loclx_process.terminate()
        sys.exit(1)

    forwarder = UdpForwarder(local_port)
    forwarder.start()

    print("[SERVER] Press Ctrl+C to stop, or close terminal.")

    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down.")
    finally:
        forwarder.stop()
        if loclx_process and loclx_process.poll() is None:
            loclx_process.terminate()

if __name__ == "__main__":
    main()
