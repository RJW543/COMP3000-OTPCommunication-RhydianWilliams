import requests
import random
import string
from pathlib import Path

# Random.org API Key (example placeholder)
API_KEY = 'e02643a9-6574-4a3a-b2a8-14b7c13d80c5'

def fetch_random_seed():
    """Fetch a random seed from Random.org."""
    url = "https://api.random.org/json-rpc/4/invoke"
    headers = {'Content-Type': 'application/json'}
    data = {
        "jsonrpc": "2.0",
        "method": "generateStrings",
        "params": {
            "apiKey": API_KEY,
            "n": 1,
            "length": 32,
            "characters": string.ascii_uppercase + string.digits + string.punctuation,
            "replacement": True
        },
        "id": 1
    }
    
    response = requests.post(url, json=data, headers=headers)
    response_data = response.json()
    if "error" in response_data:
        raise ValueError(f"Random.org API error: {response_data['error']['message']}")
    return response_data['result']['random']['data'][0]

def generate_safe_identifier(length=8):
    """
    Generate an identifier using only uppercase letters and digits,
    so it won't conflict with special protocol chars like | or :.
    """
    safe_chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(safe_chars) for _ in range(length))

def generate_random_string(length):
    """
    Generate a random string (OTP content) using uppercase letters,
    digits, and punctuation. This is for the body of the OTP page.
    """
    return ''.join(random.choice(string.ascii_uppercase + string.digits + string.punctuation)
                   for _ in range(length))

def generate_otp_page(identifier_length=8, page_length=5000):
    """
    Generate a single OTP page with:
      - 8-char safe identifier
      - the rest is random OTP content
    """
    identifier = generate_safe_identifier(identifier_length)
    otp_content = generate_random_string(page_length - identifier_length)
    return identifier + otp_content

def generate_otp_file(file_name="otp_cipher.txt", num_pages=10000, page_length=5000):
    """Generate an OTP file with each page on a new line, seeded with random.org."""
    random_seed = fetch_random_seed()
    random.seed(random_seed)  # Seed our local generator with true random data

    output_path = Path(file_name)
    with output_path.open("w") as file:
        for _ in range(num_pages):
            otp_page = generate_otp_page(page_length=page_length)
            file.write(otp_page + "\n")

    print(f"{num_pages} OTP pages generated and saved to {output_path.resolve()}.")

if __name__ == "__main__":
    generate_otp_file()
