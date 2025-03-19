import socket
import threading
import tkinter as tk
import queue
import subprocess

# UDPChat is responsible for handling the UDP socket communication.
class UDPChat:
    def __init__(self, local_port, remote_ip, remote_port, gui_callback):
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.gui_callback = gui_callback
        self.running = True

        # Create UDP socket and set it up to allow immediate reuse of the port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.local_port))

        # Start the thread to listen for incoming messages.
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

    def receive_messages(self):
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)  # buffer size 1024 bytes
                message = data.decode("utf-8")
                # Use the callback (which queues the message for the GUI) to display incoming text.
                self.gui_callback("Friend: " + message)
            except Exception as e:
                # When shutting down, the socket may be closed causing an exception.
                break

    def send_message(self, message):
        try:
            self.sock.sendto(message.encode("utf-8"), (self.remote_ip, self.remote_port))
        except Exception as e:
            print("Error sending message:", e)

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except Exception:
            pass

# ChatGUI handles the Tkinter interface and integrates with the UDPChat class.
class ChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("UDP Chat")

        # Create a frame for configuration (local port, remote IP/port, tunnel button)
        config_frame = tk.Frame(root)
        config_frame.pack(pady=5)

        tk.Label(config_frame, text="Local Port:").grid(row=0, column=0)
        self.local_port_entry = tk.Entry(config_frame, width=6)
        self.local_port_entry.grid(row=0, column=1)
        self.local_port_entry.insert(0, "5005")  # default port

        tk.Label(config_frame, text="Remote IP:").grid(row=0, column=2)
        self.remote_ip_entry = tk.Entry(config_frame, width=15)
        self.remote_ip_entry.grid(row=0, column=3)
        self.remote_ip_entry.insert(0, "127.0.0.1")  # default IP; change for your remote tunnel address

        tk.Label(config_frame, text="Remote Port:").grid(row=0, column=4)
        self.remote_port_entry = tk.Entry(config_frame, width=6)
        self.remote_port_entry.grid(row=0, column=5)
        self.remote_port_entry.insert(0, "5005")  # default port

        # Button to start a localxpose UDP tunnel (requires "loclx" to be installed and in PATH)
        self.tunnel_button = tk.Button(config_frame, text="Start Tunnel", command=self.start_tunnel)
        self.tunnel_button.grid(row=0, column=6, padx=5)

        # Create a text widget to display the conversation
        self.chat_log = tk.Text(root, height=15, width=50)
        self.chat_log.pack(padx=10, pady=5)
        self.chat_log.config(state=tk.DISABLED)

        # Frame for the message input and send button
        message_frame = tk.Frame(root)
        message_frame.pack(pady=5)
        self.message_entry = tk.Entry(message_frame, width=40)
        self.message_entry.grid(row=0, column=0, padx=5)
        self.send_button = tk.Button(message_frame, text="Send", command=self.send_message)
        self.send_button.grid(row=0, column=1)

        # A connect button to initialize the UDP socket after entering configuration
        self.connect_button = tk.Button(root, text="Connect", command=self.connect_chat)
        self.connect_button.pack(pady=5)

        # A queue to safely pass messages from the network thread to the GUI thread.
        self.msg_queue = queue.Queue()

        self.chat = None
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.check_incoming_messages()

    def start_tunnel(self):
        local_port = self.local_port_entry.get()
        # Attempt to start a UDP tunnel using localxpose with the "loclx" command.
        try:
            result = subprocess.run(
                ["loclx", "tunnel", "udp", "--local-port", local_port],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.append_message("Tunnel started successfully.\n")
            else:
                self.append_message("Tunnel failed: " + result.stderr + "\n")
        except Exception as e:
            self.append_message("Error starting tunnel: " + str(e) + "\n")

    def connect_chat(self):
        try:
            local_port = int(self.local_port_entry.get())
            remote_ip = self.remote_ip_entry.get()
            remote_port = int(self.remote_port_entry.get())
            self.chat = UDPChat(local_port, remote_ip, remote_port, self.queue_message)
            self.append_message("Connected. Listening on port {}.\n".format(local_port))
        except Exception as e:
            self.append_message("Error connecting chat: " + str(e) + "\n")

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
        if message and self.chat:
            self.chat.send_message(message)
            self.append_message("You: " + message + "\n")
            self.message_entry.delete(0, tk.END)

    def on_closing(self):
        if self.chat:
            self.chat.stop()
        self.root.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    gui = ChatGUI(root)
    root.mainloop()
