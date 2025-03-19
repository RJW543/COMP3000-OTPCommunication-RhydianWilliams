import socket
import threading
import tkinter as tk
import queue

class UDPClient:
    def __init__(self, local_port, server_ip, server_port, gui_callback):
        self.local_port = local_port
        self.server_ip = server_ip
        self.server_port = server_port
        self.gui_callback = gui_callback
        self.running = True

        # Create UDP socket and bind to the local port for receiving messages.
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.local_port))

        # Start a background thread to listen for incoming messages.
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

    def receive_messages(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = data.decode("utf-8")
                # Callback to pass the message to the GUI.
                self.gui_callback("Server: " + message)
            except Exception as e:
                break

    def send_message(self, message):
        try:
            # Send messages to the forwarding server.
            self.sock.sendto(message.encode("utf-8"), (self.server_ip, self.server_port))
        except Exception as e:
            print("Error sending message:", e)

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass

class ClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP Chat Client via Forwarding Server")

        # Frame for connection configuration (local port and server details)
        config_frame = tk.Frame(root)
        config_frame.pack(pady=5)

        tk.Label(config_frame, text="Local Port:").grid(row=0, column=0)
        self.local_port_entry = tk.Entry(config_frame, width=6)
        self.local_port_entry.grid(row=0, column=1)
        self.local_port_entry.insert(0, "5005")  # Default local port

        tk.Label(config_frame, text="Server IP:").grid(row=0, column=2)
        self.server_ip_entry = tk.Entry(config_frame, width=15)
        self.server_ip_entry.grid(row=0, column=3)
        self.server_ip_entry.insert(0, "127.0.0.1")  # Default server IP; change to your tunnel address

        tk.Label(config_frame, text="Server Port:").grid(row=0, column=4)
        self.server_port_entry = tk.Entry(config_frame, width=6)
        self.server_port_entry.grid(row=0, column=5)
        self.server_port_entry.insert(0, "6000")  # Default server port

        # Button to connect to the forwarding server.
        self.connect_button = tk.Button(root, text="Connect", command=self.connect_client)
        self.connect_button.pack(pady=5)

        # Text widget to display the chat history.
        self.chat_log = tk.Text(root, height=15, width=50)
        self.chat_log.pack(padx=10, pady=5)
        self.chat_log.config(state=tk.DISABLED)

        # Frame for message input.
        message_frame = tk.Frame(root)
        message_frame.pack(pady=5)
        self.message_entry = tk.Entry(message_frame, width=40)
        self.message_entry.grid(row=0, column=0, padx=5)
        self.send_button = tk.Button(message_frame, text="Send", command=self.send_message)
        self.send_button.grid(row=0, column=1)

        # Queue to safely pass network messages to the GUI thread.
        self.msg_queue = queue.Queue()

        self.client = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_incoming_messages()

    def connect_client(self):
        try:
            local_port = int(self.local_port_entry.get())
            server_ip = self.server_ip_entry.get()
            server_port = int(self.server_port_entry.get())
            self.client = UDPClient(local_port, server_ip, server_port, self.queue_message)
            self.append_message("Connected. Listening on local port {}.\n".format(local_port))
        except Exception as e:
            self.append_message("Error connecting client: " + str(e) + "\n")

    def queue_message(self, message):
        self.msg_queue.put(message)

    def check_incoming_messages(self):
        while not self.msg_queue.empty():
            msg = self.msg_queue.get()
            self.append_message(msg + "\n")
        self.root.after(100, self.check_incoming_messages)

    def append_message(self, message):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, message)
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.see(tk.END)

    def send_message(self):
        message = self.message_entry.get()
        if message and self.client:
            self.client.send_message(message)
            self.append_message("You: " + message + "\n")
            self.message_entry.delete(0, tk.END)

    def on_closing(self):
        if self.client:
            self.client.stop()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    gui = ClientGUI(root)
    root.mainloop()
