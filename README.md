# Autonomous Hexapod Robot 🕷️

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-green.svg)

<img width="741" height="522" alt="เดินห้นา" src="https://github.com/user-attachments/assets/31771184-d1a6-4224-acc9-65cae2604ed0" />

## 📖 Project Overview
This repository contains the source code and documentation for the **Autonomous Hexapod Robot**, my university engineering senior project. The robot is designed for exploration and navigation in hazardous or inaccessible environments. It features precise multi-axis locomotion and a real-time computer vision system.

## ✨ Key Features
* **Multi-Axis Locomotion:** Smooth and precise six-legged movement controlled via dedicated servo controllers.
* **Real-Time Computer Vision:** Low-latency live video streaming and image processing using `picamera2` and OpenCV.
* **Wireless Operation:** Robust remote control system via Wi-Fi for seamless navigation and telemetry data transmission.

## 🛠️ Tech Stack & Hardware
**Hardware:**
* Raspberry Pi 5
* Custom Hexapod Chassis (Metal/Acrylic)
* High-Torque Servo Motors & Controllers
* Camera Module

**Software:**
* **Language:** Python
* **Libraries:** OpenCV, picamera2, Socket (for Wi-Fi communication)
* **OS:** Raspberry Pi OS (Raspbian)

## 🚀 How to Run
1. Clone this repository: `git clone https://github.com/sbirds/hexapod-robot.git`
2. Install required dependencies: `pip install -r requirements.txt`
3. Run the main control script on Raspberry Pi: `python main.py`

## 👥 Authors
This senior project was co-developed by a team of two:

* **Mr.Patiphat Sombat**
  * **Role:** Hardware Design & Integration, UI/UX Design, and Software Collaboration.
  * [Email](mailto:patiphat.birds@gmail.com)
* **Mr.Sathaporn Wongwaikitkajohn**
  * **Role:** Programmer (Python, OpenCV) and Core System Architecture.
  * [Email](mailto:mr.sathaporn5451@gmail.com)
