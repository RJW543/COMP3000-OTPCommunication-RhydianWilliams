#!/bin/bash

# Define colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check the status of a command
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}[SUCCESS]${NC} $1"
    else
        echo -e "${RED}[ERROR]${NC} $1"
        exit 1
    fi
}

# Update system package list
echo "Updating package list..."
sudo apt update
check_status "Package list updated."

# Install Python3 and pip
echo "Installing Python3 and pip..."
sudo apt install -y python3 python3-pip
check_status "Python3 and pip installed."

# Install Tkinter for GUI
echo "Installing Tkinter..."
sudo apt install -y python3-tk
check_status "Tkinter installed."

# Install PortAudio and build essentials for audio support
echo "Installing PortAudio and build tools..."
sudo apt install -y portaudio19-dev python3-pyaudio python3-dev build-essential ffmpeg
check_status "PortAudio and related dependencies installed."

# Upgrade pip and install Python packages
echo "Installing required Python packages..."
pip3 install --upgrade pip
pip3 install requests pyttsx3 SpeechRecognition pyaudio
check_status "All required Python packages installed."

# Verify installations
echo "Verifying installations..."
python3 --version && pip3 --version && echo -e "${GREEN}[SUCCESS]${NC} Python3 and pip3 are properly installed."
python3 -m tkinter >/dev/null 2>&1 && echo -e "${GREEN}[SUCCESS]${NC} Tkinter is properly installed."

# Final message
echo -e "${GREEN}All dependencies installed successfully!${NC}"
