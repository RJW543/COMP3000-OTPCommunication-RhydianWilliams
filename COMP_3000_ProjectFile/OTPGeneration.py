import secrets
import string
from pathlib import Path

def generate_random_string(length):
    """Generate a cryptographically secure random string of uppercase letters and digits."""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(length))

def generate_otp_page(identifier_length=8, page_length=5000):
    """Generate a single OTP page with a random identifier and OTP content."""
    identifier = generate_random_string(identifier_length)
    otp_content = ''.join(secrets.choice(string.ascii_uppercase + string.digits + string.punctuation) 
                          for _ in range(page_length - identifier_length))
    return identifier + otp_content

def generate_otp_file(file_name="otp_cipher.txt", num_pages=100, page_length=5000):
    """Generate an OTP file with a specified number of pages."""
    output_path = Path(file_name)
    with output_path.open("w") as file:
        for _ in range(num_pages):
            otp_page = generate_otp_page()
            file.write(otp_page + "\n")
    print(f"{num_pages} OTP pages have been generated and saved to {output_path.resolve()}.")

# Generate the OTP file
generate_otp_file()
