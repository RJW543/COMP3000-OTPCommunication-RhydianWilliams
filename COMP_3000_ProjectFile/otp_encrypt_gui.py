import tkinter as tk
from tkinter import messagebox, filedialog
from pathlib import Path

def load_otp_pages(file_name="otp_cipher.txt"):
    otp_pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        messagebox.showerror("Error", f"The OTP file '{file_name}' was not found.")
        return otp_pages

    with file_path.open("r") as file:
        for line in file:
            identifier = line[:8]
            content = line[8:].strip()
            otp_pages.append((identifier, content))
    return otp_pages

def load_used_pages(file_name="used_pages.txt"):
    file_path = Path(file_name)
    if not file_path.exists():
        return set()
    with file_path.open("r") as file:
        return {line.strip() for line in file}

def save_used_page(identifier, file_name="used_pages.txt"):
    with open(file_name, "a") as file:
        file.write(f"{identifier}\n")

def get_next_otp_page(otp_pages, used_identifiers):
    for identifier, content in otp_pages:
        if identifier not in used_identifiers:
            return identifier, content
    messagebox.showerror("Error", "No unused OTP pages left.")
    return None, None

def encrypt_message(message, otp_content):
    encrypted_message = []
    for i, char in enumerate(message):
        if i >= len(otp_content):
            break
        encrypted_char = chr(ord(char) ^ ord(otp_content[i]))
        encrypted_message.append(encrypted_char)
    return ''.join(encrypted_message)

def encrypt():
    otp_pages = load_otp_pages()
    used_identifiers = load_used_pages()
    otp_identifier, otp_content = get_next_otp_page(otp_pages, used_identifiers)
    
    if otp_identifier and otp_content:
        user_message = text_input.get("1.0", tk.END).strip()
        encrypted_message = encrypt_message(user_message, otp_content)
        output_text.set(f"OTP Identifier: {otp_identifier}\nEncrypted Message: {encrypted_message}")

        with open("encrypted_message.txt", "w") as file:
            file.write(f"{otp_identifier}:{encrypted_message}\n")
        
        save_used_page(otp_identifier)
        messagebox.showinfo("Success", "Message encrypted and saved to 'encrypted_message.txt'.")

# GUI setup
root = tk.Tk()
root.title("OTP Encryption")

frame = tk.Frame(root)
frame.pack(padx=10, pady=10)

tk.Label(frame, text="Enter Message to Encrypt:").grid(row=0, column=0, sticky="w")
text_input = tk.Text(frame, height=5, width=50)
text_input.grid(row=1, column=0, pady=5)

encrypt_button = tk.Button(frame, text="Encrypt", command=encrypt)
encrypt_button.grid(row=2, column=0, pady=5)

output_text = tk.StringVar()
output_label = tk.Label(frame, textvariable=output_text, wraplength=400)
output_label.grid(row=3, column=0, pady=10)

root.mainloop()
