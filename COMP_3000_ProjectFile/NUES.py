import tkinter as tk
import socket
import threading
import subprocess
import queue
import re
import time

class VoiceBridgeServer:
    def __init__(self, master):
        self.master = master
        self.master.title("Voice Bridge Server (LocalXpose)")

        # Server/Networking
        self.server_socket = None
        self.client_sockets = []
        self.is_server_running = False
        self.bridge_threads = []

        # LocalXpose
        self.lx_process = None
        self.lx_output_queue = queue.Queue()
        self.lx_public_url = None

        # GUI Variables
        self.port_var = tk.StringVar(value="5000")
        self.lx_domain_var = tk.StringVar(value="(No tunnel yet)")

        self.create_widgets()

    def create_widgets(self):
        # Local TCP Port
        tk.Label(self.master, text="Local Port:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        tk.Entry(self.master, textvariable=self.port_var).grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Start & Stop server
        self.start_button = tk.Button(self.master, text="Start Server", command=self.start_server)
        self.start_button.grid(row=1, column=0, padx=5, pady=5)

        self.stop_button = tk.Button(self.master, text="Stop Server", command=self.stop_server, state="disabled")
        self.stop_button.grid(row=1, column=1, padx=5, pady=5)

        # LocalXpose domain info
        tk.Label(self.master, text="Public URL:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        tk.Label(self.master, textvariable=self.lx_domain_var, fg="blue").grid(row=2, column=1, padx=5, pady=5, sticky="w")

    def start_server(self):
        if self.is_server_running:
            return

        local_port = int(self.port_var.get())
        try:
            # 1) Start local server on 127.0.0.1
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(("127.0.0.1", local_port))
            self.server_socket.listen(2)  
            self.is_server_running = True

            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")

            # Accept connections in background
            threading.Thread(target=self.accept_clients, daemon=True).start()

            # 2) Start LocalXpose tunnel using loclx
            self.start_localxpose(local_port)

        except Exception as e:
            print("Error starting server:", e)

    def accept_clients(self):
        """
        Accept exactly two clients, then start bridging data between them.
        """
        self.client_sockets = []
        print("Waiting for 2 clients to connect locally (via LocalXpose tunnel)...")

        try:
            while len(self.client_sockets) < 2 and self.is_server_running:
                client_socket, addr = self.server_socket.accept()
                self.client_sockets.append(client_socket)
                print(f"Client connected: {addr} (Total = {len(self.client_sockets)})")

            if len(self.client_sockets) == 2:
                # Start bridging these two sockets
                print("2 clients connected. Starting bridging threads.")
                c1, c2 = self.client_sockets[0], self.client_sockets[1]

                # Thread: c1 -> c2
                t1 = threading.Thread(target=self.bridge_data, args=(c1, c2), daemon=True)
                t1.start()
                self.bridge_threads.append(t1)

                # Thread: c2 -> c1
                t2 = threading.Thread(target=self.bridge_data, args=(c2, c1), daemon=True)
                t2.start()
                self.bridge_threads.append(t2)
        except Exception as e:
            print("Error accepting clients:", e)
            self.stop_server()

    def bridge_data(self, source_socket, dest_socket):
        """
        Continuously read data from source_socket and forward it to dest_socket.
        If any error occurs, we close both sockets and stop the server.
        """
        try:
            while True:
                data = source_socket.recv(4096)
                if not data:
                    break
                dest_socket.sendall(data)
        except:
            pass
        finally:
            self.stop_server()

    def start_localxpose(self, local_port):
        """
        Spawns LocalXpose in a subprocess, exposing `127.0.0.1:<local_port>`.
        We use the 'loclx' command here, as requested.
        """
        try:
            cmd = ["loclx", "tunnel", "tcp", str(local_port)]
            self.lx_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            # Read LocalXpose output in background
            threading.Thread(target=self.read_lx_output, daemon=True).start()
        except Exception as e:
            print("Could not start LocalXpose:", e)
            self.stop_server()

    def read_lx_output(self):
        """
        Continuously reads LocalXpose logs. 
        Looks for a line like: "Forwarding your port <port> -> something.loca.lt:<port>"
        Then updates self.lx_domain_var with that URL.
        """
        while True:
            if not self.lx_process:
                break
            line = self.lx_process.stdout.readline()
            if not line:
                break
            print("[LocalXpose]", line.strip())

            match = re.search(r'Forwarding your port.*->\s+(\S+:\d+)', line)
            if match:
                self.lx_public_url = match.group(1)
                self.lx_domain_var.set(self.lx_public_url)

        print("[LocalXpose] Process ended.")

    def stop_localxpose(self):
        if self.lx_process and self.lx_process.poll() is None:
            self.lx_process.terminate()
            time.sleep(0.2)
            if self.lx_process.poll() is None:
                self.lx_process.kill()
            self.lx_process = None
        self.lx_domain_var.set("(No tunnel yet)")
        self.lx_public_url = None

    def stop_server(self):
        self.is_server_running = False

        # Close the bridge threads by forcing their sockets closed
        for s in self.client_sockets:
            try:
                s.close()
            except:
                pass
        self.client_sockets = []

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        # Stop LocalXpose
        self.stop_localxpose()

        # Reset GUI
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")

    def on_closing(self):
        self.stop_server()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = VoiceBridgeServer(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
