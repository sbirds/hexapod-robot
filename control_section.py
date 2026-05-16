import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports

class ControlSection:
    def __init__(self, parent, command_callback):
        self.frame = tk.Frame(parent, bg="#f0f0f0")
        self.frame.pack(fill="both", expand=True)
        self.callback = command_callback 
        self.is_camera_open = False
        
        self.lockable_widgets = []

        self.LEGS = {
            "L1": {"coxa": 25, "femur": 26, "tibia": 27}, "L2": {"coxa": 30, "femur": 31, "tibia": 32}, "L3": {"coxa": 3,  "femur": 2,  "tibia": 1},  
            "R1": {"coxa": 18, "femur": 19, "tibia": 20}, "R2": {"coxa": 10, "femur": 11, "tibia": 12}, "R3": {"coxa": 8,  "femur": 7,  "tibia": 6},  
        }
        self.calib_offsets = {leg: {"coxa": 0, "femur": 0, "tibia": 0} for leg in self.LEGS}
        self.calib_selected_leg = "L1"

        self._init_top_ui()          
        self._init_controls_area()   
        self._init_calibrator_ui()   
        
        self.set_enabled(False)

    def _init_top_ui(self):
        self.top_frame = tk.Frame(self.frame, bg="#f0f0f0")
        self.top_frame.pack(fill="x", pady=(0, 5), anchor="n")

        self.btn_camera = tk.Button(self.top_frame, text="OPEN CAMERA", font=("Arial", 10, "bold"), 
                                    bg="white", fg="black", height=2, width=15, command=self.toggle_camera_btn)
        self.btn_camera.pack(side="left", anchor="n", padx=(0, 15))
        self.lockable_widgets.append(self.btn_camera) 

        # โซนโหมดการเดิน
        mode_frame = tk.LabelFrame(self.top_frame, text=" Walk Mode (เลือกโหมด) ", font=("Arial", 9, "bold"), bg="#f0f0f0", padx=5, pady=2)
        mode_frame.pack(side="left", anchor="n")

        self.mode_buttons = {}

        def create_mode_btn(text, mode_name, r, c, active_color):
            btn = tk.Button(mode_frame, text=text, font=("Arial", 8, "bold"), width=11, bg="#e0e0e0", fg="black")
            btn.grid(row=r, column=c, padx=2, pady=2)
            btn.config(command=lambda: self.change_walk_mode(mode_name, active_color))
            self.mode_buttons[mode_name] = btn
            self.lockable_widgets.append(btn)
            return btn

        self.btn_basic = create_mode_btn("BASIC (ปกติ)", "Basic", 0, 0, "#81C784")
        self.btn_high  = create_mode_btn("HIGH (ข้ามของ)", "HighStep", 0, 1, "#FF9800")
        self.btn_stup  = create_mode_btn("ST.UP (ขึ้น)", "StairUp", 1, 0, "#2196F3")
        self.btn_stdwn = create_mode_btn("ST.DWN (ลง)", "StairDown", 1, 1, "#2196F3")
        
        self.change_walk_mode("Basic", "#81C784")

        conn_frame = tk.LabelFrame(self.top_frame, text="Interface", font=("Arial", 10), bg="white", padx=10, pady=2)
        conn_frame.pack(side="right", fill="y")

        tk.Label(conn_frame, text="Serial NO.", bg="white").grid(row=0, column=0, sticky="e", padx=5)
        self.combo_serial = ttk.Combobox(conn_frame, width=12)
        self.combo_serial.grid(row=0, column=1, pady=2)
        self.combo_serial.bind('<Button-1>', self.refresh_serial_ports)

        tk.Label(conn_frame, text="Baud Rate", bg="white").grid(row=1, column=0, sticky="e", padx=5)
        self.combo_baud = ttk.Combobox(conn_frame, width=12, values=["9600", "57600", "115200"])
        self.combo_baud.current(2)
        self.combo_baud.grid(row=1, column=1, pady=2)

        self.btn_connect = tk.Button(conn_frame, text="Connect", font=("Arial", 9, "bold"), bg="#2196F3", fg="red", width=15)
        self.btn_connect.grid(row=2, column=0, columnspan=2, pady=(5, 5))
        self.btn_connect.config(command=self.on_click_connect)
        self.refresh_serial_ports(None)

    def change_walk_mode(self, mode, active_color):
        self.callback("STOP_MOVE", None) # สั่งหยุดเดินก่อนเปลี่ยนโหมด ป้องกันหุ่นกระตุก

        for m, btn in self.mode_buttons.items():
            btn.config(bg="#e0e0e0", fg="black", relief="raised")
        self.mode_buttons[mode].config(bg=active_color, fg="white", relief="sunken")
        self.callback("SET_MODE", mode)

    def _init_controls_area(self):
        self.middle_frame = tk.Frame(self.frame, bg="#f0f0f0")
        self.middle_frame.pack(fill="x", anchor="n", pady=5)

        self._init_movement_controls()
        self._init_stand_sit_height()

    def _init_movement_controls(self):
        self.arrows_frame = tk.Frame(self.middle_frame, bg="#f0f0f0")
        self.arrows_frame.pack(side="left")

        # [NEW] คืนชีพกลับมาใช้ระบบ กดค้าง=เดิน / ปล่อย=หยุด
        def create_hold_button(text, command_name, row, col):
            btn = tk.Button(self.arrows_frame, text=text, font=("Arial", 16, "bold"), width=5, height=2)
            btn.grid(row=row, column=col, padx=4, pady=4)
            btn.bind('<ButtonPress-1>', lambda event: self.callback("START_MOVE", command_name))
            btn.bind('<ButtonRelease-1>', lambda event: self.callback("STOP_MOVE", None))
            self.lockable_widgets.append(btn)
            return btn

        create_hold_button("↺", "Rotate Left",  0, 0)
        create_hold_button("▲", "Forward",      0, 1)
        create_hold_button("↻", "Rotate Right", 0, 2) 
        create_hold_button("◀", "Turn Left",    1, 0)
        create_hold_button("▼", "Backward",     1, 1)
        create_hold_button("▶", "Turn Right",   1, 2) 

        tk.Label(self.arrows_frame, text="กดค้าง=เดิน / ปล่อย=หยุด", font=("Arial", 9), bg="#f0f0f0", fg="red").grid(row=2, column=0, columnspan=3, pady=2)

    def _init_stand_sit_height(self):
        self.current_height = 90  
        self.right_col_frame = tk.Frame(self.middle_frame, bg="#f0f0f0")
        self.right_col_frame.pack(side="right", fill="y")
        
        tk.Label(self.right_col_frame, text="ลุก/นั่ง & ความสูง", font=("Arial", 10, "bold"), bg="#f0f0f0", fg="#333").pack(pady=(0, 5))

        self.btn_stand = tk.Button(self.right_col_frame, text="STAND (ยืน)", font=("Arial", 9, "bold"), width=10, height=1, bd=2, relief="raised")
        self.btn_stand.pack(pady=2)
        self.btn_stand.bind('<Button-1>', lambda e: self.callback("ACTION", "Stand"))
        self.lockable_widgets.append(self.btn_stand)
        
        self.btn_sit = tk.Button(self.right_col_frame, text="SIT (นั่ง)", font=("Arial", 9, "bold"), width=10, height=1, bd=2, relief="raised")
        self.btn_sit.pack(pady=2)
        self.btn_sit.bind('<Button-1>', lambda e: self.callback("ACTION", "Sit"))
        self.lockable_widgets.append(self.btn_sit)
        
        height_frame = tk.LabelFrame(self.right_col_frame, text=" H: Height ", font=("Arial", 8), bg="white", padx=10, pady=2)
        height_frame.pack(pady=5, fill="x")
        
        self.btn_h_up = tk.Button(height_frame, text="▲ UP", font=("Arial", 9, "bold"), width=10, height=1, bg="#4CAF50", fg="white", relief="raised")
        self.btn_h_up.pack(pady=2)
        self.btn_h_up.bind('<Button-1>', lambda e: self.adjust_height(15))
        self.lockable_widgets.append(self.btn_h_up)

        self.lbl_height = tk.Label(height_frame, text=f"H: {self.current_height}", font=("Arial", 11, "bold"), bg="white", fg="#000")
        self.lbl_height.pack(pady=2)

        self.btn_h_down = tk.Button(height_frame, text="▼ DWN", font=("Arial", 9, "bold"), width=10, height=1, bg="#f44336", fg="white", relief="raised")
        self.btn_h_down.pack(pady=2)
        self.btn_h_down.bind('<Button-1>', lambda e: self.adjust_height(-15))
        self.lockable_widgets.append(self.btn_h_down)

    def _init_calibrator_ui(self):
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x', pady=10)

        calib_container = tk.LabelFrame(self.frame, text=" Hexapod Calibration Tool (ปรับศูนย์มอเตอร์) ", font=("Arial", 10, "bold"), bg="#f0f0f0", padx=10, pady=5)
        calib_container.pack(fill="both", expand=True)

        left_calib = tk.Frame(calib_container, bg="#f0f0f0")
        left_calib.pack(side="left", fill="y", padx=(0, 15))
        
        tk.Label(left_calib, text="1. เลือกขาที่ต้องการจูน", font=("Arial", 9), bg="#f0f0f0").grid(row=0, column=0, columnspan=2, pady=(0, 5))
        
        tk.Button(left_calib, text="L1 (หน้าซ้าย)", width=12, command=lambda: self.calib_select_leg("L1")).grid(row=1, column=0, padx=2, pady=2)
        tk.Button(left_calib, text="R1 (หน้าขวา)", width=12, command=lambda: self.calib_select_leg("R1")).grid(row=1, column=1, padx=2, pady=2)
        tk.Button(left_calib, text="L2 (กลางซ้าย)", width=12, command=lambda: self.calib_select_leg("L2")).grid(row=2, column=0, padx=2, pady=2)
        tk.Button(left_calib, text="R2 (กลางขวา)", width=12, command=lambda: self.calib_select_leg("R2")).grid(row=2, column=1, padx=2, pady=2)
        tk.Button(left_calib, text="L3 (หลังซ้าย)", width=12, command=lambda: self.calib_select_leg("L3")).grid(row=3, column=0, padx=2, pady=2)
        tk.Button(left_calib, text="R3 (หลังขวา)", width=12, command=lambda: self.calib_select_leg("R3")).grid(row=3, column=1, padx=2, pady=2)
        
        self.lbl_calib_selected = tk.Label(left_calib, text="Selected: L1", font=("Arial", 11, "bold"), fg="blue", bg="#f0f0f0")
        self.lbl_calib_selected.grid(row=4, column=0, columnspan=2, pady=5)

        right_calib = tk.Frame(calib_container, bg="#f0f0f0")
        right_calib.pack(side="left", fill="both", expand=True)

        tk.Label(right_calib, text="2. เลื่อนปรับจุดกึ่งกลาง (Center = 1500)", font=("Arial", 9), bg="#f0f0f0").pack(anchor="w", pady=(0, 5))

        def create_calib_slider(label_text, joint_type):
            frame = tk.Frame(right_calib, bg="#f0f0f0")
            frame.pack(fill="x", pady=2)
            tk.Label(frame, text=label_text, width=12, anchor="w", bg="#f0f0f0").pack(side="left")
            
            scale = tk.Scale(frame, from_=1000, to=2000, orient="horizontal", bg="#f0f0f0", length=150)
            scale.config(command=lambda v: self.calib_update_servo(joint_type, v))
            scale.set(1500)
            scale.pack(side="left", fill="x", expand=True, padx=5)
            
            lbl = tk.Label(frame, text="Off: 0", width=6, fg="red", bg="#f0f0f0")
            lbl.pack(side="right")
            
            self.lockable_widgets.append(scale) 
            return scale, lbl

        self.sl_coxa, self.lbl_off_coxa = create_calib_slider("Coxa (โคน)", "coxa")
        self.sl_femur, self.lbl_off_femur = create_calib_slider("Femur (ต้น)", "femur")
        self.sl_tibia, self.lbl_off_tibia = create_calib_slider("Tibia (ปลาย)", "tibia")

        self.btn_reset_calib = tk.Button(right_calib, text="RESET (คืนค่าเดิม 1500)", bg="#f44336", fg="white", font=("Arial", 9, "bold"), command=self.calib_reset_leg)
        self.btn_reset_calib.pack(pady=5, anchor="e")
        self.lockable_widgets.append(self.btn_reset_calib)

    def calib_select_leg(self, leg_name):
        self.calib_selected_leg = leg_name
        self.lbl_calib_selected.config(text=f"Selected: {leg_name}")
        off = self.calib_offsets[leg_name]
        self.sl_coxa.set(1500 + off["coxa"]); self.sl_femur.set(1500 + off["femur"]); self.sl_tibia.set(1500 + off["tibia"])

    def calib_update_servo(self, joint_type, val_str):
        pwm = int(val_str); offset = pwm - 1500
        self.calib_offsets[self.calib_selected_leg][joint_type] = offset
        txt = f"Off: {offset}"
        if joint_type == "coxa": self.lbl_off_coxa.config(text=txt)
        elif joint_type == "femur": self.lbl_off_femur.config(text=txt)
        elif joint_type == "tibia": self.lbl_off_tibia.config(text=txt)
        pin = self.LEGS[self.calib_selected_leg][joint_type]
        self.callback("CALIB_SERVO", (pin, pwm))

    def calib_reset_leg(self):
        self.sl_coxa.set(1500); self.sl_femur.set(1500); self.sl_tibia.set(1500)

    def refresh_serial_ports(self, event):
        ports = serial.tools.list_ports.comports()
        self.combo_serial['values'] = [p.device for p in ports]
        if self.combo_serial['values'] and self.combo_serial.get() == "": self.combo_serial.current(0)

    def on_click_connect(self):
        port = self.combo_serial.get(); baud = self.combo_baud.get()
        if port == "":
            messagebox.showwarning("Warning", "Please select a Serial Port!")
            return
        self.callback("CONNECT", (port, baud))

    def toggle_camera_btn(self): self.callback("CAMERA_TOGGLE", None)

    def set_connect_status(self, is_connected):
        if is_connected:
            self.btn_connect.config(text="Disconnect", bg="#4CAF50", fg="white"); self.set_enabled(True) 
        else:
            self.btn_connect.config(text="Connect", bg="#2196F3", fg="red"); self.set_enabled(False) 

    def set_camera_status(self, is_open):
        self.is_camera_open = is_open
        if is_open: self.btn_camera.config(bg="#90EE90", text="CAMERA ON")
        else: self.btn_camera.config(bg="white", text="OPEN CAMERA")

    def set_enabled(self, is_enabled):
        for widget in self.lockable_widgets: widget.config(state="normal" if is_enabled else "disabled")

    def adjust_height(self, step):
        self.current_height = max(0, min(180, self.current_height + step))
        self.lbl_height.config(text=f"H: {self.current_height}")
        self.callback("HEIGHT", self.current_height)