import random
from pathlib import Path

# Base64 character set
BASE64_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"

def generate_random_string(length):
    return ''.join(random.choice(BASE64_CHARS) for _ in range(length))

def generate_otp_file(file_name="otp_cipher.txt", num_pages=10000, page_length=3500, identifier_length=8):
    random.seed()
    output_path = Path(file_name)

    with output_path.open("w", encoding="utf-8") as file:
        for _ in range(num_pages):
            identifier = generate_random_string(identifier_length)
            otp_content = generate_random_string(page_length - identifier_length)
            file.write(identifier + otp_content + "\n")

    return output_path.resolve()

if __name__ == "__main__":
    path = generate_otp_file()
    print(f"OTP file generated at: {path}")
