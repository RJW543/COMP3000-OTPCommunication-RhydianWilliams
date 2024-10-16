import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path

def load_otp_pages(file_name="otp_cipher.txt"):
    otp_pages = {}
    file_path = Path(file_name)
    if not file_path.exists():
        messagebox.showerror("Error", f"The OTP file '{file_name}' was not found.")
        return otp_pages

    with file_path.open("r") as file:
        for line in file:
            identifier = line[:8]
            content = line[8:].strip()
            otp_pages[identifier] = content
    return otp_pages

def decrypt_message(encrypted_message, otp_content):
    decrypted_message = []
    for i, char in enumerate(encrypted_message):
        if i >= len(otp_content):
            break
        decrypted_char = chr(ord(char) ^ ord(otp_content[i]))
        decrypted_message.append(decrypted_char)
    return ''.join(decrypted_message)

def load_encrypted_message(file_name="encrypted_message.txt"):
    file_path = Path(file_name)
    if not file_path.exists():
        messagebox.showerror("Error", f"The encrypted message file '{file_name}' was not found.")
        return None, None

    with file_path.open("r") as file:
        line = file.readline().strip()
        identifier, encrypted_message = line.split(":", 1)
    return identifier, encrypted_message

def decrypt():
    otp_pages = load_otp_pages()
    otp_identifier, encrypted_message = load_encrypted_message()

    if otp_identifier and encrypted_message:
        if otp_identifier not in otp_pages:
            messagebox.showerror("Error", f"OTP identifier '{otp_identifier}' not found.")
            return

        otp_content = otp_pages[otp_identifier]
        decrypted_message = decrypt_message(encrypted_message, otp_content)
        output_text.set(f"Decrypted Message: {decrypted_message}")

        with open("decrypted_message.txt", "w") as file:
            file.write(decrypted_message)
        
        messagebox.showinfo("Success", "Message decrypted and saved to 'decrypted_message.txt'.")

# GUI setup
root = tk.Tk()
root.title("OTP Decryption")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

decrypt_button = tk.Button(frame, text="Decrypt", command=decrypt)
decrypt_button.grid(row=0, column=0, pady=10)

output_text = tk.StringVar()
output_label = tk.Label(frame, textvariable=output_text, wraplength=400)
output_label.grid(row=1, column=0, pady=10)

root.mainloop()
