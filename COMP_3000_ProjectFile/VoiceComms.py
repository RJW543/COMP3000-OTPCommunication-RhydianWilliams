import tkinter as tk
from tkinter import messagebox
import threading
from pyngrok import ngrok
from pyVoIP.VoIP import VoIPServer, VoIPClient

# Configuration
NGROK_PORT = 5060  

def start_ngrok():
    """Start ngrok tunnel."""
    tunnel = ngrok.connect(NGROK_PORT, "tcp")
    public_url = tunnel.public_url.replace("tcp://", "")
    return public_url

def start_voip_server():
    """Start a simple VoIP server."""
    server = VoIPServer("0.0.0.0", NGROK_PORT)
    server.start()

def call_peer():
    """Initiate a VoIP call to the entered peer."""
    peer_address = peer_entry.get()
    if not peer_address:
        messagebox.showerror("Error", "Please enter a valid ngrok number!")
        return
    
    try:
        client = VoIPClient()
        client.call(peer_address)
        messagebox.showinfo("Success", "Calling " + peer_address)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to call: {str(e)}")

# GUI Setup
root = tk.Tk()
root.title("VoIP Call System")
root.geometry("300x200")

tk.Label(root, text="Enter ngrok address:").pack(pady=5)
peer_entry = tk.Entry(root, width=30)
peer_entry.pack(pady=5)

tk.Button(root, text="Call", command=call_peer).pack(pady=10)

# Start VoIP Server in a separate thread
server_thread = threading.Thread(target=start_voip_server, daemon=True)
server_thread.start()

# Start ngrok and display its address
ngrok_address = start_ngrok()
tk.Label(root, text=f"Your ngrok address: {ngrok_address}").pack(pady=5)

root.mainloop()
