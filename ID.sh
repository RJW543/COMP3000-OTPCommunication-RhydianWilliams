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

# Install Python3
echo "Installing Python3..."
sudo apt install -y python3 python3-pip
check_status "Python3 and pip installed."

# Install Tkinter (required for GUI)
echo "Installing Tkinter..."
sudo apt install -y python3-tk
check_status "Tkinter installed."

# Install other necessary Python packages
echo "Installing required Python packages..."
pip3 install --upgrade pip
pip3 install requests
check_status "Required Python packages installed."

# Verify installations
echo "Verifying installations..."
python3 --version && pip3 --version && echo -e "${GREEN}[SUCCESS]${NC} Python3 and pip3 are properly installed."
python3 -m tkinter >/dev/null 2>&1 && echo -e "${GREEN}[SUCCESS]${NC} Tkinter is properly installed."

# Final message
echo -e "${GREEN}All dependencies installed successfully!${NC}"
