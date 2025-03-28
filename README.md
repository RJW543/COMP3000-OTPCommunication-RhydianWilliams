# COMP3000-OTPCommunication-RhydianWilliams
Student name: Rhydian Williams <br>
<br>
Allocated supervisor: Dr Hai-Van Dang <br>
<br>
Project title: Overcoming the practical challenges in implementing one-time pads for delayed and real time bi-directional communication <br>
<br>
Project Vision: This project is designed for individuals or institutions whose need is to send text and voice communications with unbreakable encryption. The aim of this project is to develop a practical encryption system for text and voice communications that will provide perfect encryption using one time pads. <br>

# 🔐 Secure OTP-based Communication System

This project provides a secure communication solution using One-Time Pad (OTP) encryption, ensuring theoretically unbreakable text and voice communication. It leverages Python applications, utilising secure encryption mechanisms to protect privacy against interception.

---

## 🚀 Features

- **Secure End-to-End Encryption**: Using One-Time Pads (OTP)
- **Integrated Communication**: Supports both text and voice
- **Intuitive GUI**: User-friendly graphical interface
- **Easy Setup**: Single launcher for all functions
- **Works with voice**: Recording, transcription, encryption, and playback

---

## 🛠️ Getting Started

### 📋 Prerequisites

Ensure you have **Python 3.8 or higher** installed.

---

### 💻 Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/RJW543/COMP3000-OTPCommunication-RhydianWilliams.git
```
#### 2. Install Dependencies
```bash
pip install tkinter pyngrok SpeechRecognition pyttsx3 pyaudio
```

### Dependencies Explained:
- tkinter: Python’s built-in GUI toolkit
- pyngrok: Secure public URL tunneling
- SpeechRecognition: Voice transcription capabilities
- pyttsx3: Text-to-speech conversion
- pyaudio: Microphone input handling (used by SpeechRecognition)
Note: If you face issues installing pyaudio, check the [PyAudio Installation Guide.](https://people.csail.mit.edu/hubert/pyaudio/#downloads)

---

⚙️ Configuration

### Setting Up pyngrok

Securely forward traffic by configuring your pyngrok authentication token:

1. Sign up at Ngrok.
3. Obtain your authtoken from your Ngrok dashboard.
3. Configure your token by running:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```
Replace YOUR_NGROK_AUTHTOKEN with your actual token.

---

▶️ Usage

### Launching the Application

Start the launcher GUI to manage server and client applications:
```bash
python3 launcher.py
```

#### Generating and Sharing OTP
- Use launcher.py to access GenGUI.py and generate a One-Time Pad (OTP).
- securely share the generated OTP file with your communication partner to enable encrypted communication.

### 📂 Included Applications
| File | Description | 
|----------|----------|
| launcher.py | Centralised launcher GUI  | 
| TextASG.py  | Handles server-side encrypted text-based communication  | 
| VoiceAC.py | Manages encrypted voice and text communication  | 
| GenGUI.py  | Generates new One-Time Pads (OTPs)  | 

---

### 🔒 Security and Ethical Notice
This system is intended solely for ethical and legal purposes. Users must adhere to applicable laws and ethical standards concerning data privacy and encryption.

---
Open source and free for anyone to use 
