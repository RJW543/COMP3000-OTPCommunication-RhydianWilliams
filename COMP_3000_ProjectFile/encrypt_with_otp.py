from pathlib import Path

def load_otp_pages(file_name="otp_cipher.txt"):
    """Load OTP pages from the file and return them as a list of (identifier, content)."""
    otp_pages = []
    file_path = Path(file_name)
    if not file_path.exists():
        raise FileNotFoundError(f"The OTP file '{file_name}' was not found.")

    with file_path.open("r") as file:
        for line in file:
            identifier = line[:8]
            content = line[8:].strip()
            otp_pages.append((identifier, content))
    return otp_pages

def load_used_pages(file_name="used_pages.txt"):
    """Load used OTP identifiers from the file and return them as a set."""
    file_path = Path(file_name)
    if not file_path.exists():
        return set()  # Return an empty set if the file does not exist

    with file_path.open("r") as file:
        return {line.strip() for line in file}

def save_used_page(identifier, file_name="used_pages.txt"):
    """Save the used OTP identifier to the file."""
    with open(file_name, "a") as file:
        file.write(f"{identifier}\n")

def get_next_otp_page(otp_pages, used_identifiers):
    """Find the next unused OTP page based on identifiers."""
    for identifier, content in otp_pages:
        if identifier not in used_identifiers:
            return identifier, content
    raise ValueError("No unused OTP pages left.")

def encrypt_message(message, otp_content):
    """Encrypt the message using the OTP content."""
    encrypted_message = []
    for i, char in enumerate(message):
        if i >= len(otp_content):
            break
        encrypted_char = chr(ord(char) ^ ord(otp_content[i]))
        encrypted_message.append(encrypted_char)
    return ''.join(encrypted_message)

def main():
    otp_pages = load_otp_pages()
    used_identifiers = load_used_pages()
    
    # Get the next available OTP page
    otp_identifier, otp_content = get_next_otp_page(otp_pages, used_identifiers)
    user_message = input("Enter the message to encrypt: ")
    
    # Encrypt the user's message
    encrypted_message = encrypt_message(user_message, otp_content)

    print(f"OTP Identifier: {otp_identifier}")
    print(f"Encrypted Message: {encrypted_message}")

    # Save the encrypted message and OTP identifier to a file
    with open("encrypted_message.txt", "w") as file:
        file.write(f"{otp_identifier}:{encrypted_message}\n")
    print("The encrypted message has been saved to 'encrypted_message.txt'.")

    # Mark the current OTP page as used
    save_used_page(otp_identifier)

if __name__ == "__main__":
    main()
