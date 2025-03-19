import tkinter as tk
import socket
import threading

class UDPServerApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Server Side - LocalXpose Relay")

        # GUI elements
        self.local_port_label = tk.Label(master, text="Local Listen Port:")
        self.local_port_label.pack(pady=2)
        self.local_port_entry = tk.Entry(master)
        self.local_port_entry.insert(0, "9999")  # default
        self.local_port_entry.pack(pady=2)

        self.lx_host_label = tk.Label(master, text="LocalXpose Host (e.g. myapp.loclx.io):")
        self.lx_host_label.pack(pady=2)
        self.lx_host_entry = tk.Entry(master)
        self.lx_host_entry.insert(0, "myapp.loclx.io")  # example, replace as needed
        self.lx_host_entry.pack(pady=2)

        self.lx_port_label = tk.Label(master, text="LocalXpose Port (e.g. 9999):")
        self.lx_port_label.pack(pady=2)
        self.lx_port_entry = tk.Entry(master)
        self.lx_port_entry.insert(0, "9999")  # example
        self.lx_port_entry.pack(pady=2)

        self.start_button = tk.Button(master, text="Start Server", command=self.start_server)
        self.start_button.pack(pady=5)

        self.info_label = tk.Label(master, text="")
        self.info_label.pack(pady=5)

        self.client_addrs_label = tk.Label(master, text="Known Clients: None")
        self.client_addrs_label.pack(pady=5)

        self.last_message_label = tk.Label(master, text="Last Received Text: None")
        self.last_message_label.pack(pady=5)

        # Dictionary to track clients: { name: (ip, port) }
        self.client_registry = {}

        self.sock = None
        self.running = False

    def start_server(self):
        if self.sock is not None:
            self.info_label.config(text="Server already started.")
            return

        # Get user input
        local_port_str = self.local_port_entry.get().strip()
        lx_host = self.lx_host_entry.get().strip()
        lx_port_str = self.lx_port_entry.get().strip()

        # Validate inputs
        if not local_port_str.isdigit() or not lx_port_str.isdigit():
            self.info_label.config(text="Please enter valid numeric ports.")
            return

        local_port = int(local_port_str)
        lx_port = int(lx_port_str)

        # Create and bind socket
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(("", local_port))  # bind locally
        except Exception as e:
            self.info_label.config(text=f"Error binding server: {e}")
            self.sock = None
            return

        self.info_label.config(
            text=f"Server listening on local port {local_port}. "
                 f"\nLocalXpose Domain: {lx_host}:{lx_port}\n"
                 f"(Give this domain/port to clients.)"
        )

        self.running = True
        self.listener_thread = threading.Thread(target=self.listen_udp, daemon=True)
        self.listener_thread.start()

    def listen_udp(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                text_received = data.decode("utf-8", errors="ignore").strip()

                # Check if this is a registration packet: "REGISTER: SomeName"
                if text_received.startswith("REGISTER:"):
                    name = text_received.split(":", 1)[1].strip()
                    self.client_registry[name] = addr

                    # Update our label with known clients
                    self.client_addrs_label.config(
                        text="Known Clients:\n" +
                        "\n".join([
                            f"{n} @ {ip}:{port}"
                            for n, (ip, port) in self.client_registry.items()
                        ])
                    )
                    continue

                if ":" not in text_received:
                    continue  # ignore malformed

                sender_name, message = text_received.split(":", 1)
                sender_name = sender_name.strip()
                message = message.strip()

                # Update server GUI
                self.last_message_label.config(
                    text=f"From {sender_name}: {message}"
                )

                # Forward the text to every other registered client
                for name, client_addr in self.client_registry.items():
                    if name == sender_name:
                        continue  # skip self
                    self.sock.sendto(data, client_addr)

            except Exception as e:
                print(f"Server error: {e}")
                break

    def on_closing(self):
        self.running = False
        if self.sock:
            self.sock.close()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = UDPServerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
