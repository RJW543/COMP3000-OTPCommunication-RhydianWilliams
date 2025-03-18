import tkinter as tk
import socket
import threading

class UDPServerApp:
    def __init__(self, master, server_port=9999):
        self.master = master
        self.master.title("Server Side - LocalXpose Relay")

        # GUI elements
        self.info_label = tk.Label(master, text="LocalXpose UDP Relay Server")
        self.info_label.pack(pady=5)

        self.port_label = tk.Label(master, text=f"Listening on UDP port: {server_port}")
        self.port_label.pack(pady=5)

        self.client_addrs_label = tk.Label(master, text="Known Clients: None")
        self.client_addrs_label.pack(pady=5)

        self.last_message_label = tk.Label(master, text="Last Received Text: None")
        self.last_message_label.pack(pady=5)

        # Maintain a dict of client_name -> (ip, port)
        self.client_registry = {}

        # Start UDP socket
        self.server_port = server_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", self.server_port))

        # Thread to handle incoming messages
        self.running = True
        self.listener_thread = threading.Thread(target=self.listen_udp, daemon=True)
        self.listener_thread.start()

    def listen_udp(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
                text_received = data.decode("utf-8", errors="ignore").strip()

                if text_received.startswith("REGISTER:"):
                    name = text_received.split(":", 1)[1].strip()
                    self.client_registry[name] = addr

                    self.client_addrs_label.config(
                        text="Known Clients: " + ", ".join(
                            [f"{n}@{ip}:{port}" for n, (ip, port) in self.client_registry.items()]
                        )
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

                for name, client_addr in self.client_registry.items():
                    if name == sender_name:
                        continue  # don't send to self
                    self.sock.sendto(text_received.encode("utf-8"), client_addr)

            except Exception as e:
                print(f"Server error: {e}")
                break

    def on_closing(self):
        self.running = False
        self.sock.close()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = UDPServerApp(root, server_port=9999)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
