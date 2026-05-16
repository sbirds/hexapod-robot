# Hexapod Robot 🕷️

![Python](https://img.shields.io/badge/Python-3.x-blue.svg)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-5-C51A4A.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-green.svg)

<img width="741" height="522" alt="เดินห้นา" src="https://github.com/user-attachments/assets/31771184-d1a6-4224-acc9-65cae2604ed0" />

## 🖥 Display Control
<img width="384" height="229" alt="รูปภาพ1" src="https://github.com/user-attachments/assets/b9dec662-af93-4cd8-a2be-64f9a26dd959" />

## 📖 Project Overview
This repository contains the source code and documentation for the **Autonomous Hexapod Robot**, my university engineering senior project. The robot is designed for exploration and navigation in hazardous or inaccessible environments. It features precise multi-axis locomotion and a real-time computer vision system.

## ✨ Key Features
* **Multi-Axis Locomotion:** Smooth and precise six-legged movement controlled via dedicated servo controllers.
* **Real-Time Computer Vision:** Low-latency live video streaming and image processing using `picamera2` and OpenCV.
* **Wireless Operation:** Robust remote control system via Wi-Fi for seamless navigation and telemetry data transmission.

## 🛠️ Tech Stack & Hardware
**Hardware:**
* **Main Board:** Raspberry Pi 5 (4GB RAM)
* **Servo Controller:** RTrobot 32-Channel Servo Controller (VER 3.1)
* **Actuators:** 19x Servo Motor MG996R (18 for legs, 1 for camera pan)
* **Camera:** Arducam 5MP Camera Board
* **Power Supply:** LiPo Battery 3S 11.1V 6000mAh 40C
* **Power Management:** LTC3780 DC-DC Step-Down & XL4016E1 DC-DC Step-Down Converters
* **Chassis:** Aluminum Hexapod Robot Model
* **Other:** 3-Pin Red Switch

**Software & Tools:**
* **Programming Language:** Python
* **Libraries:** OpenCV (cv2), picamera2, PySerial, NumPy, Tkinter, Pillow
* **Servo Configuration Tool:** RTrobot Servo Controller (Ver 3.7.6)
* **Remote Control & Monitoring:** Raspberry Pi Connect / RealVNC
* **IDE:** Visual Studio Code (VS Code)
* **OS:** Raspberry Pi OS (Linux)

## 🚀 How to Run
1. Clone this repository: 
   `git clone https://github.com/sbirds/hexapod-robot.git`
2. Navigate to the project directory: 
   `cd hexapod-robot`
3. Install required dependencies: 
   `pip3 install -r requirements.txt`
4. Run the main control script on Raspberry Pi: 
   `python3 main.py`

## 👥 Authors
This senior project was co-developed by a team of two:

* **Mr.Patiphat Sombat**
  * **Role:** Hardware Design & Integration, UI/UX Design, and Software Collaboration.
  * [Email](mailto:patiphat.birds@gmail.com)
* **Mr.Sathaporn Wongwaikitkajohn**
  * **Role:** Programmer (Python, OpenCV) and Core System Architecture.
  * [Email](mailto:mr.sathaporn5451@gmail.com)
