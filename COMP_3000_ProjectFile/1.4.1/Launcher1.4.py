import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

class MainMenuApp:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Main Menu")

        tk.Label(master, text="Please choose an action:", font=("Arial", 14)).pack(pady=10)

        btn_host_server = tk.Button(master, text="Host Server", width=20, command=self.launch_server_gui)
        btn_host_server.pack(pady=5)

        btn_run_client = tk.Button(master, text="Run Client", width=20, command=self.launch_client_gui)
        btn_run_client.pack(pady=5)

        btn_generate_otp = tk.Button(master, text="Generate a new OTP", width=20, command=self.launch_gen_gui)
        btn_generate_otp.pack(pady=5)

        self.script_dir = Path(__file__).parent

    def launch_server_gui(self):
        try:
            subprocess.Popen([sys.executable, self.script_dir / "TextASG1.4.py"])
        except FileNotFoundError:
            messagebox.showerror("Error", "Could not find or launch TextASG1.4.py")

    def launch_client_gui(self):
        try:
            subprocess.Popen([sys.executable, self.script_dir / "VoiceAC1.4.py"])
        except FileNotFoundError:
            messagebox.showerror("Error", "Could not find or launch VoiceAC1.4.py")

    def launch_gen_gui(self):
        try:
            subprocess.Popen([sys.executable, self.script_dir / "GenGUI1.4.py"])
        except FileNotFoundError:
            messagebox.showerror("Error", "Could not find or launch GenGUI1.4.py")


def main():
    root = tk.Tk()
    app = MainMenuApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
