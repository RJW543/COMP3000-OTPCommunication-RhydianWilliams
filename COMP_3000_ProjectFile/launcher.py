import tkinter as tk
import subprocess
import sys

class MainMenuApp:
    def __init__(self, master):
        self.master = master
        self.master.title("OTP Main Menu")

        # Label / Title
        tk.Label(master, text="Please choose an action:", font=("Arial", 14)).pack(pady=10)

        # Buttons
        btn_host_server = tk.Button(master, text="Host a Server", width=20, command=self.launch_server_gui)
        btn_host_server.pack(pady=5)

        btn_run_client = tk.Button(master, text="Run Client", width=20, command=self.launch_client_gui)
        btn_run_client.pack(pady=5)

        btn_generate_otp = tk.Button(master, text="Generate a new OTP", width=20, command=self.launch_gen_gui)
        btn_generate_otp.pack(pady=5)

    def launch_server_gui(self):
        """
        Launch Attempt2SG.py (the server GUI).
        """
        try:
            subprocess.Popen([sys.executable, "Attempt2SG.py"])
        except FileNotFoundError:
            # If Attempt2SG.py isn't found or can't be launched
            tk.messagebox.showerror("Error", "Could not find or launch Attempt2SG.py")

    def launch_client_gui(self):
        """
        Launch Attempt2C.py (the client GUI).
        """
        try:
            subprocess.Popen([sys.executable, "Attempt2C.py"])
        except FileNotFoundError:
            tk.messagebox.showerror("Error", "Could not find or launch Attempt2C.py")

    def launch_gen_gui(self):
        """
        Launch GenGUI.py (the OTP generator GUI).
        """
        try:
            subprocess.Popen([sys.executable, "GenGUI.py"])
        except FileNotFoundError:
            tk.messagebox.showerror("Error", "Could not find or launch GenGUI.py")


def main():
    root = tk.Tk()
    app = MainMenuApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
