"""
encrypt_voice.py

Records audio from the microphone, encrypts it in real time using a one-time pad (OTP)
stored in otp_cipher.txt, and saves the encrypted data to an output file.

The OTP file is generated as a text file where each page is a single line of 5000 characters.
The first 8 characters of each page are used for synchronization and are skipped when
reading pad data.
"""

import pyaudio
import argparse

PAGE_SIZE = 5000    # each OTP page is 5000 characters
HEADER_SIZE = 8     # first 8 characters (sync header) are not used for encryption

class OTPReader:
    """
    Reads OTP bytes from a text file (otp_cipher.txt) while automatically skipping
    the first HEADER_SIZE characters of each PAGE_SIZE block.
    """
    def __init__(self, filename, page_size=PAGE_SIZE, header_size=HEADER_SIZE):
        self.page_size = page_size
        self.header_size = header_size
        # Read the OTP file in text mode and remove newline characters.
        with open(filename, 'r') as f:
            lines = f.read().splitlines()
        otp_string = ''.join(lines)
        if len(otp_string) % page_size != 0:
            print("Warning: OTP file length is not an exact multiple of the page size!")
        # Convert the OTP string to bytes 
        self.data = otp_string.encode('ascii')
        self.current_index = 0

    def read(self, n):
        """
        Return n bytes from the OTP pad, skipping over header bytes on each page.
        """
        result = bytearray()
        while len(result) < n:
            # Compute the start of the current OTP page.
            current_page_start = (self.current_index // self.page_size) * self.page_size
            # If the current index is within the header, skip to the end of header.
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

def encrypt_audio(otp_filename, output_filename, record_seconds):
    FORMAT = pyaudio.paInt16    # 16-bit audio
    CHANNELS = 1                # mono audio
    RATE = 16000                # 16 kHz sample rate 
    CHUNK = 1024                # number of frames per buffer

    print("Loading OTP file:", otp_filename)
    otp = OTPReader(otp_filename)

    p = pyaudio.PyAudio()
    print("Opening microphone stream...")
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("Recording and encrypting for {} seconds...".format(record_seconds))
    total_chunks = int(RATE / CHUNK * record_seconds)
    with open(output_filename, 'wb') as outf:
        try:
            for _ in range(total_chunks):
                # Read a chunk of raw audio data.
                audio_data = stream.read(CHUNK)
                # Get the same number of OTP bytes.
                otp_bytes = otp.read(len(audio_data))
                # XOR the audio data with the OTP bytes.
                encrypted_chunk = bytes(a ^ b for a, b in zip(audio_data, otp_bytes))
                outf.write(encrypted_chunk)
        except KeyboardInterrupt:
            print("Recording interrupted by user.")
    print("Encryption complete. Encrypted data saved to", output_filename)

    stream.stop_stream()
    stream.close()
    p.terminate()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Encrypt real-time voice messages using a one-time pad.")
    parser.add_argument("--otp", type=str, default="otp_cipher.txt",
                        help="Path to the OTP file (default: otp_cipher.txt)")
    parser.add_argument("--output", type=str, default="encrypted_audio.bin",
                        help="Output file for encrypted audio (default: encrypted_audio.bin)")
    parser.add_argument("--duration", type=int, default=10,
                        help="Recording duration in seconds (default: 10)")
    args = parser.parse_args()
    encrypt_audio(args.otp, args.output, args.duration)
