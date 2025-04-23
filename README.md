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
- **Chat History & OTP Management**: Per‑user chat logs and automatic tracking/locking of used OTP pages (used_pages.txt).

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

| Step | DAction | 
|----------|----------|
| Generate OTP | $ python3 Launcher1.4.py → Generate a new OTP → choose pages & mode.File otp_cipher.txt appears in the same folder – copy it (securely!) to every client. | 
| Start Server | server GUI  | 
| VoiceAC1.4.py | In the launcher click Host Server.The server window shows a green Server is RUNNING message plus Ngrok Host and Port. Share these with your peers.  | 
| Run Client   | On each client machine: Run Client → enter Ngrok host/port → set a unique userID → Connect.  | 
| Send | Choose a recipient ID, type a message or press Record Voice Message, then Send.  | 

### 📂 Project Structure (v1.4)
| File | Description | 
|----------|----------|
| Launcher1.4.py  | main menu  | 
| TextASG1.4.py  | server GUI  | 
| VoiceAC1.4.py | client GUI (text + voice)  | 
| GenGUI1.4.py   | OTP generator GUI  | 
| otp_cipher.txt | generated OTP pages (not version‑controlled)  | 
| used_pages.txt  | consumed OTP identifiers (auto‑created)  | 
| chat_history_<userID>.txt  | per‑user logs (auto‑created) | 
---

### 🔒 Security and Ethical Notice
This software is provided solely for lawful and educational purposes.  Users are responsible for complying with all applicable laws and regulations.  Misuse of strong encryption to facilitate illegal activity is strictly discouraged.
---
Open source and free for anyone to use 
