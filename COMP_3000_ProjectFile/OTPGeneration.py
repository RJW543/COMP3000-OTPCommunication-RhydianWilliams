import requests
import random
import string
from pathlib import Path

# Random.org API Key
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

def generate_random_string(length):
    """Generate a random string using a locally seeded pseudo-random generator."""
    return ''.join(random.choice(string.ascii_uppercase + string.digits + string.punctuation) for _ in range(length))

def generate_otp_page(identifier_length=8, page_length=5000):
    """Generate a single OTP page with a random identifier and OTP content."""
    identifier = generate_random_string(identifier_length)
    otp_content = generate_random_string(page_length - identifier_length)
    return identifier + otp_content

def generate_otp_file(file_name="otp_cipher.txt", num_pages=10000, page_length=5000):
    """Generate an OTP file with each page written vertically (one per line), seeded with true random data."""
    # Fetch a single true random seed
    random_seed = fetch_random_seed()
    random.seed(random_seed)  # Seed the pseudo-random generator with true random data

    output_path = Path(file_name)
    with output_path.open("w") as file:
        for _ in range(num_pages):
            otp_page = generate_otp_page()
            # Write each page on a new line
            file.write(otp_page + "\n")
    print(f"{num_pages} OTP pages have been generated and saved to {output_path.resolve()}.")

# Generate the OTP file
generate_otp_file()
