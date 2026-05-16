import serial
import time

# ===============================================================
# ตั้งค่าการเชื่อมต่อ (แก้ไขตรงนี้ให้ตรงกับคอมของคุณ)
# ===============================================================
# Windows: 'COM3', 'COM4', ...
# Mac/Linux: '/dev/ttyUSB0', '/dev/ttyACM0', ...
SERIAL_PORT = '/dev/ttyACM0' 
BAUD_RATE = 115200

# ===============================================================
# Mapping ขา (อิงตาม main.py ของคุณ)
# ===============================================================
LEGS = {
    # --- ฝั่งซ้าย (Left) ---
    "L1": {"coxa": 25, "femur": 26,  "tibia": 27}, 
    "L2": {"coxa": 30, "femur": 31,  "tibia": 32}, 
    "L3": {"coxa": 3,  "femur": 2, "tibia": 1},  
    
    # --- ฝั่งขวา (Right) ---
    "R1": {"coxa": 18, "femur": 19, "tibia": 20}, 
    "R2": {"coxa": 10, "femur": 11, "tibia": 12}, 
    "R3": {"coxa": 8,  "femur": 7, "tibia": 6},  
}

def set_all_servos_to_center():
    print(f"Connecting to {SERIAL_PORT} at {BAUD_RATE}...")
    
    try:
        # เปิดการเชื่อมต่อ
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2) # รอให้บอร์ดรีเซ็ตตัวเองแป๊บนึง (บางบอร์ดต้องรอ)
        
        print("Sending command: All Servos -> 1500 (90 deg)...")
        
        cmd = ""
        count = 0
        
        # วนลูปดึงเลขขามาสร้างคำสั่ง
        for leg_name, pins in LEGS.items():
            for part_name, pin_id in pins.items():
                # สร้างคำสั่ง #ID P1500
                cmd += f"#{pin_id}P1500 "
                count += 1
        
        # เพิ่มเวลาให้ขยับ T1000 (1 วินาที)
        full_cmd = cmd + "T1000\r\n"
        
        # ส่งข้อมูล
        ser.write(full_cmd.encode('utf-8'))
        
        print(f"Success! Sent 1500 to {count} servos.")
        print("Please mount your servo horns at 90 degrees (Perpendicular/Right Angle).")
        
        # ปิดการเชื่อมต่อ
        ser.close()
        
    except serial.SerialException as e:
        print(f"[Error] Could not connect to port {SERIAL_PORT}")
        print(f"Details: {e}")
        print("Did you check your COM Port number?")

if __name__ == "__main__":
    set_all_servos_to_center()