import tkinter as tk
from tkinter import messagebox
import threading
from pyngrok import ngrok
from pyVoIP.VoIP import VoIPPhone

# Configuration
NGROK_PORT = 5060  # Standard SIP port

def start_ngrok():
    """Start ngrok tunnel."""
    global ngrok_address_label
    tunnel = ngrok.connect(NGROK_PORT, "tcp")
    public_url = tunnel.public_url.replace("tcp://", "")
    ngrok_address_label.config(text=f"Your ngrok address: {public_url}")

def start_voip_server():
    """Start a simple VoIP phone server."""
    phone = VoIPPhone()
    
    def on_incoming_call(call):
        call.answer()
        print("Incoming call answered!")

    phone.on_call_received = on_incoming_call
    phone.start()

def call_peer():
    """Initiate a VoIP call to the entered peer."""
    peer_address = peer_entry.get()
    if not peer_address:
        messagebox.showerror("Error", "Please enter a valid ngrok number!")
        return
    
    try:
        phone = VoIPPhone()
        phone.start()
        call = phone.call(peer_address)
        messagebox.showinfo("Success", "Calling " + peer_address)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to call: {str(e)}")

# GUI Setup
root = tk.Tk()
root.title("VoIP Call System")
root.geometry("300x250")

tk.Label(root, text="Enter ngrok address:").pack(pady=5)
peer_entry = tk.Entry(root, width=30)
peer_entry.pack(pady=5)

tk.Button(root, text="Start ngrok", command=start_ngrok).pack(pady=5)
ngrok_address_label = tk.Label(root, text="Your ngrok address: Not started")
ngrok_address_label.pack(pady=5)

tk.Button(root, text="Call", command=call_peer).pack(pady=10)

# Start VoIP Server in a separate thread
server_thread = threading.Thread(target=start_voip_server, daemon=True)
server_thread.start()

root.mainloop()
