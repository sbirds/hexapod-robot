import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports

class CalibratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hexapod Calibration Tool (Find Offsets)")
        # ปรับขนาดเริ่มต้นให้กว้างขึ้นหน่อย ความสูงพอดีๆ
        self.root.geometry("600x650")
        
        # --- Config & Variables ---
        self.ser = None
        self.is_connected = False
        
        # Mapping ขา (ต้องตรงกับ main.py)
        self.LEGS = {
            "L1": {"coxa": 25, "femur": 26, "tibia": 27}, 
            "L2": {"coxa": 30, "femur": 31, "tibia": 32}, 
            "L3": {"coxa": 3,  "femur": 2,  "tibia": 1},  
            "R1": {"coxa": 18, "femur": 19, "tibia": 20}, 
            "R2": {"coxa": 10, "femur": 11, "tibia": 12}, 
            "R3": {"coxa": 8,  "femur": 7,  "tibia": 6},  
        }

        # เก็บค่า Offset ที่จูนได้
        self.offsets = {} 
        for leg in self.LEGS:
            self.offsets[leg] = {"coxa": 0, "femur": 0, "tibia": 0}

        self.selected_leg = "L1" # ขาที่กำลังจูน

        # --- UI Setup ---
        # ใช้ Canvas + Scrollbar เพื่อป้องกันหน้าจอเล็กเกินไป (ถ้าจำเป็น) แต่จัด Layout ใหม่น่าจะพอ
        self.main_container = tk.Frame(self.root)
        self.main_container.pack(fill="both", expand=True, padx=10, pady=5)

        self._init_connection_ui()
        self._init_selection_ui()
        self._init_sliders_ui()
        self._init_result_ui()

    def _init_connection_ui(self):
        frame = tk.LabelFrame(self.main_container, text="1. Connection", padx=5, pady=5)
        frame.pack(fill="x", pady=5)
        
        # Port Selection
        self.combo_ports = ttk.Combobox(frame, width=15)
        self.combo_ports.pack(side="left", padx=5)
        self.combo_ports.bind('<Button-1>', self.refresh_ports)
        
        # Baud
        self.combo_baud = ttk.Combobox(frame, width=10, values=["9600", "115200"])
        self.combo_baud.current(1)
        self.combo_baud.pack(side="left", padx=5)
        
        # Button
        self.btn_connect = tk.Button(frame, text="Connect", bg="#DDD", command=self.toggle_connect)
        self.btn_connect.pack(side="left", padx=5)

    def _init_selection_ui(self):
        frame = tk.LabelFrame(self.main_container, text="2. Select Leg to Calibrate", padx=5, pady=5)
        frame.pack(fill="x", pady=5)
        
        legs_frame = tk.Frame(frame)
        legs_frame.pack()
        
        # Row 1
        tk.Button(legs_frame, text="L1 (Front Left)", width=12, command=lambda: self.select_leg("L1")).grid(row=0, column=0, padx=2, pady=2)
        tk.Button(legs_frame, text="R1 (Front Right)", width=12, command=lambda: self.select_leg("R1")).grid(row=0, column=1, padx=2, pady=2)
        # Row 2
        tk.Button(legs_frame, text="L2 (Mid Left)", width=12, command=lambda: self.select_leg("L2")).grid(row=1, column=0, padx=2, pady=2)
        tk.Button(legs_frame, text="R2 (Mid Right)", width=12, command=lambda: self.select_leg("R2")).grid(row=1, column=1, padx=2, pady=2)
        # Row 3
        tk.Button(legs_frame, text="L3 (Back Left)", width=12, command=lambda: self.select_leg("L3")).grid(row=2, column=0, padx=2, pady=2)
        tk.Button(legs_frame, text="R3 (Back Right)", width=12, command=lambda: self.select_leg("R3")).grid(row=2, column=1, padx=2, pady=2)
        
        self.lbl_selected = tk.Label(frame, text="Selected: L1", font=("Arial", 12, "bold"), fg="blue")
        self.lbl_selected.pack(pady=5)

    def _init_sliders_ui(self):
        self.slider_frame = tk.LabelFrame(self.main_container, text="3. Adjust PWM (Center = 1500)", padx=5, pady=5)
        self.slider_frame.pack(fill="x", pady=5)
        
        # Helper function สร้าง Slider
        def create_slider(label_text, command_func):
            frame = tk.Frame(self.slider_frame)
            frame.pack(fill="x", pady=2)
            tk.Label(frame, text=label_text, width=15, anchor="w").pack(side="left")
            scale = tk.Scale(frame, from_=1000, to=2000, orient="horizontal", command=command_func)
            scale.set(1500)
            scale.pack(side="left", fill="x", expand=True)
            lbl = tk.Label(frame, text="Off: 0", width=8, fg="red")
            lbl.pack(side="right")
            return scale, lbl

        self.sl_coxa, self.lbl_off_coxa = create_slider("Coxa (โคน)", lambda v: self.update_servo("coxa", v))
        self.sl_femur, self.lbl_off_femur = create_slider("Femur (ต้น)", lambda v: self.update_servo("femur", v))
        self.sl_tibia, self.lbl_off_tibia = create_slider("Tibia (ปลาย)", lambda v: self.update_servo("tibia", v))

    def _init_result_ui(self):
        frame = tk.LabelFrame(self.main_container, text="4. Result (Copy to ik_engine.py)", padx=5, pady=5)
        frame.pack(fill="both", expand=True, pady=5)
        
        # [แก้ไข] ย้ายปุ่มมาไว้ข้างบน และทำให้ใหญ่ขึ้น สีเขียวสด
        btn = tk.Button(frame, text="GENERATE CODE (Click Here)", bg="#00C853", fg="white", 
                        font=("Arial", 11, "bold"), command=self.generate_code)
        btn.pack(fill="x", padx=10, pady=(5, 5))
        
        self.txt_result = tk.Text(frame, height=6, font=("Consolas", 9))
        self.txt_result.pack(fill="both", expand=True, padx=5, pady=5)
        
    # --- Logic ---
    def refresh_ports(self, event):
        ports = serial.tools.list_ports.comports()
        self.combo_ports['values'] = [p.device for p in ports]

    def toggle_connect(self):
        if not self.is_connected:
            try:
                port = self.combo_ports.get()
                baud = self.combo_baud.get()
                if not port: return
                self.ser = serial.Serial(port, int(baud), timeout=1)
                self.is_connected = True
                self.btn_connect.config(text="Disconnect", bg="green", fg="white")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        else:
            self.ser.close()
            self.is_connected = False
            self.btn_connect.config(text="Connect", bg="#DDD", fg="black")

    def select_leg(self, leg_name):
        self.selected_leg = leg_name
        self.lbl_selected.config(text=f"Selected: {leg_name}")
        
        off = self.offsets[leg_name]
        self.sl_coxa.set(1500 + off["coxa"])
        self.sl_femur.set(1500 + off["femur"])
        self.sl_tibia.set(1500 + off["tibia"])

    def update_servo(self, joint_type, val_str):
        if not self.is_connected: return
        
        pwm = int(val_str)
        offset = pwm - 1500
        
        self.offsets[self.selected_leg][joint_type] = offset
        
        # Update labels
        txt = f"Off: {offset}"
        if joint_type == "coxa": self.lbl_off_coxa.config(text=txt)
        elif joint_type == "femur": self.lbl_off_femur.config(text=txt)
        elif joint_type == "tibia": self.lbl_off_tibia.config(text=txt)

        # Send Command
        pin = self.LEGS[self.selected_leg][joint_type]
        cmd = f"#{pin}P{pwm}T100\r\n"
        self.ser.write(cmd.encode())

    def generate_code(self):
        code = "LEG_OFFSETS = {\n"
        for leg in ["L1", "L2", "L3", "R1", "R2", "R3"]:
            off = self.offsets[leg]
            code += f'    "{leg}": {{"coxa": {off["coxa"]}, "femur": {off["femur"]}, "tibia": {off["tibia"]}}},\n'
        code += "}"
        
        self.txt_result.delete("1.0", tk.END)
        self.txt_result.insert(tk.END, code)
        
if __name__ == "__main__":
    root = tk.Tk()
    app = CalibratorApp(root)
    root.mainloop()