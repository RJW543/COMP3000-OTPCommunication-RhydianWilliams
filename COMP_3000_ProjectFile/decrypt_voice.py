"""
decrypt_voice.py

Reads an encrypted audio file (encrypted using a one-time pad) and decrypts it in real time.
The OTP file (otp_cipher.txt) is used to generate the OTP bytes – skipping the first 8 characters
of each 5000-character page – to XOR with the encrypted data. The resulting audio is played.
"""

import pyaudio
import argparse

PAGE_SIZE = 5000    # each OTP page is 5000 characters
HEADER_SIZE = 8     # first 8 characters are the sync header

class OTPReader:
    """
    Reads OTP bytes from the OTP file (otp_cipher.txt) while automatically skipping the
    header bytes at the start of each page.
    """
    def __init__(self, filename, page_size=PAGE_SIZE, header_size=HEADER_SIZE):
        self.page_size = page_size
        self.header_size = header_size
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        otp_string = ''.join(lines)
        if len(otp_string) % page_size != 0:
            print("Warning: OTP file length is not an exact multiple of the page size!")
        self.data = otp_string.encode('ascii')
        self.current_index = 0

    def read(self, n):
        """
        Return n OTP bytes (skipping header portions on each page).
        """
        result = bytearray()
        while len(result) < n:
            current_page_start = (self.current_index // self.page_size) * self.page_size
            if self.current_index < current_page_start + self.header_size:
                self.current_index = current_page_start + self.header_size
            current_page_end = current_page_start + self.page_size
            bytes_left_in_page = current_page_end - self.current_index
            to_read = min(n - len(result), bytes_left_in_page)
            if self.current_index + to_read > len(self.data):
                raise Exception("Not enough OTP data! The pad is exhausted.")
            result.extend(self.data[self.current_index:self.current_index + to_read])
            self.current_index += to_read
        return bytes(result)

def decrypt_audio(otp_filename, encrypted_filename):
    # Audio parameters 
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    CHUNK = 1024

    print("Loading OTP file:", otp_filename)
    otp = OTPReader(otp_filename)

    p = pyaudio.PyAudio()
    print("Opening audio output stream...")
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK)

    print("Decrypting and playing audio from", encrypted_filename)
    with open(encrypted_filename, 'rb') as inf:
        try:
            while True:
                encrypted_chunk = inf.read(CHUNK)
                if not encrypted_chunk:
                    break
                otp_bytes = otp.read(len(encrypted_chunk))
                # XOR decryption – same as encryption.
                decrypted_chunk = bytes(a ^ b for a, b in zip(encrypted_chunk, otp_bytes))
                stream.write(decrypted_chunk)
        except KeyboardInterrupt:
            print("Playback interrupted by user.")
    print("Decryption complete.")

    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Decrypt and play an audio message encrypted with a one-time pad.")
    parser.add_argument("--otp", type=str, default="otp_cipher.txt",
                        help="Path to the OTP file (default: otp_cipher.txt)")
    parser.add_argument("--input", type=str, default="encrypted_audio.bin",
                        help="Encrypted audio file to decrypt (default: encrypted_audio.bin)")
    args = parser.parse_args()
    decrypt_audio(args.otp, args.input)
