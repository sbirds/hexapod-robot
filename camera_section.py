import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
import cv2 

# Import picamera2
try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None
    # print("Error: picamera2 library not found!")

class CameraSection:
    def __init__(self, parent, command_callback=None):
        self.command_callback = command_callback
        self.PAN_CHANNEL = 22

        self.cap = None
        self.picam2 = None
        self.is_running = False

        self.frame = tk.Frame(parent, bg="#f0f0f0")
        self.frame.pack(fill="both", expand=True)

        # --- กรอบ Camera ---
        self.camera_label_frame = tk.LabelFrame(self.frame, text="Camera", font=("Arial", 16, "bold"), bg="white")
        self.camera_label_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        # --- หน้าจอกล้อง ---
        self.camera_screen = tk.Label(self.camera_label_frame, text="Camera OFF", bg="#333", fg="white", font=("Arial", 14))
        self.camera_screen.pack(fill="both", expand=True, padx=5, pady=5)

        # --- Slider & Reset Button ---
        self.cam_pan_label = tk.Label(self.frame, text=f"< ซ้าย (180°) --- หมุนกล้อง (Ch.{self.PAN_CHANNEL}) --- ขวา (0°) >", 
                                      bg="#f0f0f0", font=("Arial", 12), fg="#007bff")
        self.cam_pan_label.pack(pady=(0, 5))
        
        # Container สำหรับ Slider และปุ่ม Reset
        slider_frame = tk.Frame(self.frame, bg="#f0f0f0")
        slider_frame.pack(fill="x", padx=10)

        # 1. Slider (Scale)
        self.cam_pan_scale = tk.Scale(slider_frame, from_=180, to=0, orient="horizontal", command=self.on_pan_camera)
        self.cam_pan_scale.set(90) # ค่าเริ่มต้นตรงกลาง
        self.cam_pan_scale.pack(side="left", fill="x", expand=True)

        # 2. [นำกลับมา] ปุ่ม Reset Camera
        self.btn_reset = tk.Button(slider_frame, text="Reset", bg="#FFC107", font=("Arial", 9, "bold"), command=self.reset_camera)
        self.btn_reset.pack(side="right", padx=(5, 0))

        # เริ่มต้นมาให้ Lock ไว้ก่อน
        self.set_enabled(False)

    def set_enabled(self, is_enabled):
        """ ล็อค/ปลดล็อค การควบคุมกล้อง """
        state = "normal" if is_enabled else "disabled"
        self.cam_pan_scale.config(state=state)
        self.btn_reset.config(state=state) # ควบคุมสถานะปุ่ม Reset ด้วย

    def reset_camera(self):
        """ รีเซ็ตกล้องกลับไปที่ 90 องศา """
        self.cam_pan_scale.set(90)
        # Note: เมื่อ set ค่า slider จะไปเรียก on_pan_camera โดยอัตโนมัติ

    def start_camera_stream(self):
        if Picamera2 is None:
            self.camera_screen.config(text="Error: picamera2 not installed", bg="red")
            return

        if not self.is_running:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_preview_configuration(
                    main={"size": (640, 480), "format": "RGB888"}
                )
                self.picam2.configure(config)
                self.picam2.start()
                
                print("[Camera] Picamera2 Started.")
                self.is_running = True
                self.update_frame() 

            except Exception as e:
                print(f"[Error] Picamera2 failed: {e}")
                self.stop_camera_stream() 
                self.camera_screen.config(text=f"Camera Error: {e}", bg="red")

    def stop_camera_stream(self):
        self.is_running = False
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except:
                pass
            self.picam2 = None
        self.camera_screen.config(image='', text="Camera OFF", bg="#333")

    def update_frame(self):
        if self.is_running and self.picam2:
            try:
                # ดึงภาพจาก Buffer ล่าสุด (Picamera2 มักส่ง BGR ออกมา)
                frame = self.picam2.capture_array()
                if frame is not None:
                    # 1. ใช้ OpenCV ในการ Resize และ Flip
                    frame = cv2.flip(frame, -1) # กลับหัวตามการติดตั้งกล้อง
                    frame = cv2.resize(frame, (480, 360), interpolation=cv2.INTER_NEAREST) 
                    
                    # 2. [แก้สีเพี้ยน] แปลงช่องสีจาก BGR เป็น RGB ให้ PIL เข้าใจถูกต้อง
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    
                    # 3. แปลงเป็น PhotoImage เพื่อแสดงใน Tkinter
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    
                    self.camera_screen.imgtk = imgtk
                    self.camera_screen.config(image=imgtk, text="")
                
                # ปรับเป็น 33ms เพื่อให้ได้ประมาณ 30 FPS ที่คงที่
                self.camera_screen.after(33, self.update_frame)

            except Exception as e:
                print(f"Frame Error: {e}")
                self.stop_camera_stream()

    def on_pan_camera(self, val):
        degree = int(val)
        # คำนวณค่า PWM สำหรับ Servo (สูตรตัวอย่าง: ปรับตามอุปกรณ์ของคุณ)
        servo_pwm = int(500 + (degree * (2000 / 180)))
        
        # print(f"Slider Pos: {degree} -> Servo PWM: {servo_pwm}")
        if self.command_callback:
            self.command_callback("SERVO", self.PAN_CHANNEL, servo_pwm)