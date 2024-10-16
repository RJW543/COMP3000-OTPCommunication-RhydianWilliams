from pathlib import Path

def load_otp_pages(file_name="otp_cipher.txt"):
    """Load OTP pages from the file and return them as a dictionary keyed by their identifiers."""
    otp_pages = {}
    file_path = Path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"The OTP file '{file_name}' was not found.")

    with file_path.open("r") as file:
        for line in file:
            identifier = line[:8]
            content = line[8:].strip()
            otp_pages[identifier] = content
    return otp_pages

def decrypt_message(encrypted_message, otp_content):
    """Decrypt the message using the OTP content."""
    decrypted_message = []
    for i, char in enumerate(encrypted_message):
        if i >= len(otp_content):
            break
        decrypted_char = chr(ord(char) ^ ord(otp_content[i]))
        decrypted_message.append(decrypted_char)
    return ''.join(decrypted_message)

def load_encrypted_message(file_name="encrypted_message.txt"):
    """Load the encrypted message and its OTP identifier from the file."""
    file_path = Path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"The encrypted message file '{file_name}' was not found.")

    with file_path.open("r") as file:
        line = file.readline().strip()
        identifier, encrypted_message = line.split(":", 1)
    return identifier, encrypted_message

def main():
    # Load OTP pages
    otp_pages = load_otp_pages()
    
    # Load the encrypted message and its OTP identifier
    otp_identifier, encrypted_message = load_encrypted_message()

    # Get the corresponding OTP content
    if otp_identifier not in otp_pages:
        raise ValueError(f"OTP identifier '{otp_identifier}' not found in OTP file.")

    otp_content = otp_pages[otp_identifier]

    # Decrypt the message
    decrypted_message = decrypt_message(encrypted_message, otp_content)

    print(f"Decrypted Message: {decrypted_message}")

    # Save the decrypted message to a file
    with open("decrypted_message.txt", "w") as file:
        file.write(decrypted_message)
    print("The decrypted message has been saved to 'decrypted_message.txt'.")

if __name__ == "__main__":
    main()
