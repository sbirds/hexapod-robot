import tkinter as tk
from tkinter import messagebox
import serial
import time
import threading 
import math

from camera_section import CameraSection
from control_section import ControlSection
from tkinter import ttk

class RobotControllerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Robot Controller (Sequence Engine)")
        self.root.geometry("1000x650") 
        self.root.configure(bg="#f0f0f0")

        self.is_camera_open = False
        self.is_connected = False
        self.ser = None 
        self.last_sent_time = 0 
        self.send_interval = 0.1 
        self.move_thread = None
        self.stop_event = threading.Event()
        
        self.speed_mode = "Normal" 
        self.walk_mode = "Basic"  

        # 1. ประกาศความเร็ว
        # ⚡ ปรับสมดุลความเร็วใหม่ (แก้บั๊กข้อมูลล้นจนเครื่องค้าง)
        self.speed_settings = {
            # t_time ต้องน้อยกว่าหรือเท่ากับ delay เสมอครับ
            "Slow":   {"delay": 0.035, "t_time": "T35", "frames": 25}, 
            "Normal": {"delay": 0.025, "t_time": "T25", "frames": 15}, 
            "Fast":   {"delay": 0.020, "t_time": "T20", "frames": 8}   
        }

        # 2. ประกาศขาของหุ่นยนต์ (ต้องมาก่อนหน่วยความจำ)
        self.LEGS = {
            "L1": {"coxa": 25, "femur": 26, "tibia": 27}, "L2": {"coxa": 30, "femur": 31, "tibia": 32}, "L3": {"coxa": 3,  "femur": 2, "tibia": 1},  
            "R1": {"coxa": 18, "femur": 19, "tibia": 20}, "R2": {"coxa": 10, "femur": 11, "tibia": 12}, "R3": {"coxa": 8,  "femur": 7, "tibia": 6},  
        }

        self.INVERTED_FEMUR = [2, 26, 31] 
        self.COXA_DIR = {"L1": 1, "L2": 1, "L3": 1, "R1": -1, "R2": -1, "R3": -1}

        # 3. ระบบหน่วยความจำ
        self.current_pose = {k: {"coxa": 0, "femur": 0, "tibia": 0} for k in self.LEGS}
        self.current_step_index = 0
        self.last_direction = None

        # --- Top Bar ---
        self.top_bar_frame = tk.Frame(self.root, bg="#333", bd=0)
        self.top_bar_frame.pack(side="top", fill="x")

        # 4. สร้าง Status Bar (จุดที่หายไป)
        self.status_bar = tk.Label(self.top_bar_frame, text=" Status: Ready | Connection: Offline | Mode: Basic ", 
                                   font=("Arial", 11, "bold"), bg="#333", fg="white", anchor="w", padx=10)
        self.status_bar.pack(side="left", pady=8)

        # 5. สร้างปุ่ม Speed
        self._create_speed_controls(self.top_bar_frame)

        # --- Main Content ---
        self.main_content = tk.Frame(self.root, bg="#f0f0f0")
        self.main_content.pack(fill="both", expand=True)

        self.left_frame = tk.Frame(self.main_content, bg="#f0f0f0", width=450)
        self.left_frame.pack(side="left", fill="both", expand=True, padx=20, pady=20)

        self.right_frame = tk.Frame(self.main_content, bg="#f0f0f0", width=450)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.camera_ui = CameraSection(self.left_frame, command_callback=self.handle_camera_servo)
        self.control_ui = ControlSection(self.right_frame, command_callback=self.handle_control_action)

        self.height_offsets = {k: {"femur": 0, "tibia": 0} for k in self.LEGS}
        

    def handle_control_action(self, action_type, data):
        if action_type == "CONNECT": self.toggle_connection(data[0], data[1])
        elif action_type == "CAMERA_TOGGLE": self.toggle_camera()
        elif action_type == "SET_MODE":
            self.walk_mode = data
            self.update_status()
        elif action_type == "START_MOVE":
            if self.move_thread is None or not self.move_thread.is_alive():
                self.stop_event.clear()
                self.move_thread = threading.Thread(target=self.move_loop_thread, args=(data,))
                self.move_thread.start()
        elif action_type == "STOP_MOVE": self.stop_event.set()
        elif action_type == "HEIGHT": self.handle_height(data)
        elif action_type == "ACTION": self.handle_action(data)
        elif action_type == "CALIB_SERVO":
            pin, pwm = data
            self.send_command(f"#{pin}P{pwm}T100")

    # =========================================================================
    # [SEQUENCE ENGINE] เครื่องยนต์เดินด้วยระบบเฟรมแอนิเมชั่น
    # =========================================================================
    def move_loop_thread(self, direction):
        if not self.is_connected: return
        
        actual_direction = direction
        if direction == "Forward" and self.walk_mode != "Basic":
            actual_direction = self.walk_mode
            
        self.root.after(0, lambda: self.update_status(f"Walking {actual_direction}..."))

        # ดึงค่า Setting ตามความเร็วที่เลือก
        settings = self.speed_settings[self.speed_mode]
        INTERPOLATION_FRAMES = settings["frames"]
        FRAME_DELAY = settings["delay"]
        CMD_TIME    = settings["t_time"]
        
        sequence = self.get_sequence_data(actual_direction)
        if not sequence: return

        # 🧠 ระบบความทรงจำ: ถ้าเปลี่ยนทิศทาง ให้เริ่มนับก้าวใหม่
        if self.last_direction != actual_direction:
            self.current_step_index = 0
            self.last_direction = actual_direction

        # --- ลูปการเดิน ---
        while not self.stop_event.is_set():
            target_step = sequence[self.current_step_index]

            for i in range(1, INTERPOLATION_FRAMES + 1):
                if self.stop_event.is_set(): break
                t = i / INTERPOLATION_FRAMES
                # ทำความเคลื่อนไหวให้สมูทด้วย Sine Curve
                smooth_t = (1 - math.cos(t * math.pi)) / 2  
                
                cmd = ""
                for leg_name in self.LEGS:
                    start_off = self.current_pose[leg_name]
                    end_off = target_step[leg_name]
                    pins = self.LEGS[leg_name]

                    # 1. คำนวณ Coxa (ข้อต่อโคนขา)
                    curr_coxa = start_off['coxa'] + (end_off['coxa'] - start_off['coxa']) * smooth_t
                    pwm_c = max(500, min(2000, int(1500 + curr_coxa)))
                    
                    # 2. คำนวณ Femur (ข้อต่อต้นขา) - ใช้ฐาน 1500 เท่ากันทุกขา
                    curr_femur = start_off['femur'] + (end_off['femur'] - start_off['femur']) * smooth_t
                    h_off_f = self.height_offsets[leg_name]["femur"] if hasattr(self, 'height_offsets') else 0
                    final_femur = curr_femur + h_off_f
                    pwm_f = max(500, min(2000, int(1500 + final_femur)))
                    
                    # 3. คำนวณ Tibia (ข้อต่อปลายขา)
                    curr_tibia = start_off['tibia'] + (end_off['tibia'] - start_off['tibia']) * smooth_t
                    h_off_t = self.height_offsets[leg_name]["tibia"] if hasattr(self, 'height_offsets') else 0
                    final_tibia = curr_tibia + h_off_t
                    pwm_t = max(500, min(2000, int(1500 + final_tibia)))

                    cmd += f"#{pins['coxa']}P{pwm_c} #{pins['femur']}P{pwm_f} #{pins['tibia']}P{pwm_t} "
                
                self.send_command(cmd + CMD_TIME)
                time.sleep(FRAME_DELAY)
            
            # จบ 1 ก้าว เลื่อนไปก้าวต่อไปใน Sequence
            if not self.stop_event.is_set():
                self.current_pose = target_step
                self.current_step_index = (self.current_step_index + 1) % len(sequence)
        
        # ========================================================
        # ❌ ปล่อยปุ่มปุ๊บ: ชักขากลับมายืนท่าตรง (Reset ให้ตรงกับท่ายืน)
        # ========================================================
        cmd_reset = ""
        reset_pose = {k: {"coxa": 0, "femur": 0, "tibia": 0} for k in self.LEGS}
        
        for leg_name in self.LEGS: 
            pins = self.LEGS[leg_name]
            
            # ใช้ฐาน 1500 และบวกค่าความสูงปัจจุบัน (ถ้ามี) เพื่อไม่ให้หุ่นวูบ
            f_h_offset = self.height_offsets[leg_name]["femur"] if hasattr(self, 'height_offsets') else 0
            t_h_offset = self.height_offsets[leg_name]["tibia"] if hasattr(self, 'height_offsets') else 0
            
            # ยืนที่โหมดมาตรฐาน (Coxa=1500, Femur=1500+Offset, Tibia=1500+Offset)
            reset_f = max(500, min(2000, int(1500 + f_h_offset)))
            reset_t = max(500, min(2000, int(1500 + t_h_offset)))
            
            cmd_reset += f"#{pins['coxa']}P1500 #{pins['femur']}P{reset_f} #{pins['tibia']}P{reset_t} "
            
        # ค่อยๆ ทิ้งตัวลงมายืนในเวลา 1 วินาที (T1000) เพื่อความนุ่มนวล
        self.send_command(cmd_reset + "T1000")
        
        # อัปเดตสถานะหน่วยความจำว่ากลับมายืนท่าตรงแล้ว
        self.current_pose = reset_pose 
        self.root.after(0, lambda: self.update_status("Standing (Ready)"))

    def get_sequence_data(self, direction):
        reset = {k: {"coxa": 0, "femur": 0, "tibia": 0} for k in self.LEGS}

        # ========================================================
        # 🚶‍♂️ 1. การเดินหน้า (Forward) - Tripod Gait สมดุล 100%
        # ========================================================
        F_L_FWD = 180; F_L_BWD = -180  
        F_R_FWD = -140; F_R_BWD = 140  # เพิ่มระยะก้าวฝั่งขวาจาก 150 เป็น 200 เพื่อให้ก้าวยาวขึ้น
        
        UP_L = -250; 
        UP_R = 350 # เพิ่มระยะยกฝั่งขวาจาก 250 เป็น 350 เพื่อให้ยกพ้นพื้นมากขึ้น   
        DN = 0
        
        # --- เฟรม 1: Group A (L1, R2, L3) ยกก้าว | Group B (R1, L2, R3) ดันหลัง ---
        fw_1 = {
            # Group A: ยกก้าว
            "L1": {"coxa": F_L_FWD, "femur": UP_L, "tibia": 0}, "R2": {"coxa": F_R_FWD, "femur": UP_R, "tibia": 0}, "L3": {"coxa": F_L_FWD, "femur": UP_L, "tibia": 0},
            # Group B: ดันพื้นอยู่กับที่
            "R1": {"coxa": F_R_BWD, "femur": DN, "tibia": 0},   "L2": {"coxa": F_L_BWD, "femur": DN, "tibia": 0},   "R3": {"coxa": F_R_BWD, "femur": DN, "tibia": 0}
        }
        # --- เฟรม 2: Group A วางพื้น ---
        fw_2 = {
            "L1": {"coxa": F_L_FWD, "femur": DN, "tibia": 0},   "R2": {"coxa": F_R_FWD, "femur": DN, "tibia": 0},   "L3": {"coxa": F_L_FWD, "femur": DN, "tibia": 0},
            "R1": {"coxa": F_R_BWD, "femur": DN, "tibia": 0},   "L2": {"coxa": F_L_BWD, "femur": DN, "tibia": 0},   "R3": {"coxa": F_R_BWD, "femur": DN, "tibia": 0}
        }
        # --- เฟรม 3: Group B (R1, L2, R3) ยกก้าว | Group A (L1, R2, L3) ดันหลัง ---
        fw_3 = {
            # ขาฝั่งขวา R1 และ R3 ต้องใช้ UP_R (ค่าเป็นบวกเพื่อยกขึ้น)
            "R1": {"coxa": F_R_FWD, "femur": UP_R, "tibia": 0}, 
            "L2": {"coxa": F_L_FWD, "femur": UP_L, "tibia": 0}, 
            "R3": {"coxa": F_R_FWD, "femur": UP_R, "tibia": 0},
            
            # Group A ดันพื้น (ค่า femur เป็น 0 หรือ DN)
            "L1": {"coxa": F_L_BWD, "femur": DN, "tibia": 0},   
            "R2": {"coxa": F_R_BWD, "femur": DN, "tibia": 0},   
            "L3": {"coxa": F_L_BWD, "femur": DN, "tibia": 0}
        }
        # --- เฟรม 4: Group B วางพื้น ---
        fw_4 = {
            "R1": {"coxa": F_R_FWD, "femur": DN, "tibia": 0},   "L2": {"coxa": F_L_FWD, "femur": DN, "tibia": 0},   "R3": {"coxa": F_R_FWD, "femur": DN, "tibia": 0},
            "L1": {"coxa": F_L_BWD, "femur": DN, "tibia": 0},   "R2": {"coxa": F_R_BWD, "femur": DN, "tibia": 0},   "L3": {"coxa": F_L_BWD, "femur": DN, "tibia": 0}
        }

        # ========================================================
        # 🚶‍♂️ 2. การเดินถอยหลัง (Backward) - Tripod Gait สมดุล 100%
        # ========================================================
        B_L_REACH = -150; B_L_PUSH = 150  
        B_R_REACH = 150; B_R_PUSH = -150  

        # --- เฟรม 1: Group A ถอย | Group B ดันหน้า ---
        bw_1 = {
            "L1": {"coxa": B_L_REACH, "femur": UP_L, "tibia": 0}, "R2": {"coxa": B_R_REACH, "femur": UP_R, "tibia": 0}, "L3": {"coxa": B_L_REACH, "femur": UP_L, "tibia": 0},
            "R1": {"coxa": B_R_PUSH,  "femur": DN, "tibia": 0},   "L2": {"coxa": B_L_PUSH,  "femur": DN, "tibia": 0},   "R3": {"coxa": B_R_PUSH,  "femur": DN, "tibia": 0}
        }
        # --- เฟรม 2: Group A วางพื้น ---
        bw_2 = {
            "L1": {"coxa": B_L_REACH, "femur": DN, "tibia": 0},   "R2": {"coxa": B_R_REACH, "femur": DN, "tibia": 0},   "L3": {"coxa": B_L_REACH, "femur": DN, "tibia": 0},
            "R1": {"coxa": B_R_PUSH,  "femur": DN, "tibia": 0},   "L2": {"coxa": B_L_PUSH,  "femur": DN, "tibia": 0},   "R3": {"coxa": B_R_PUSH,  "femur": DN, "tibia": 0}
        }
        # --- เฟรม 3: Group B ถอย | Group A ดันหน้า ---
        bw_3 = {
            "R1": {"coxa": B_R_REACH, "femur": UP_R, "tibia": 0}, "L2": {"coxa": B_L_REACH, "femur": UP_L, "tibia": 0}, "R3": {"coxa": B_R_REACH, "femur": UP_R, "tibia": 0},
            "L1": {"coxa": B_L_PUSH,  "femur": DN, "tibia": 0},   "R2": {"coxa": B_R_PUSH,  "femur": DN, "tibia": 0},   "L3": {"coxa": B_L_PUSH,  "femur": DN, "tibia": 0}
        }
        # --- เฟรม 4: Group B วางพื้น ---
        bw_4 = {
            "R1": {"coxa": B_R_REACH, "femur": DN, "tibia": 0},   "L2": {"coxa": B_L_REACH, "femur": DN, "tibia": 0},   "R3": {"coxa": B_R_REACH, "femur": DN, "tibia": 0},
            "L1": {"coxa": B_L_PUSH,  "femur": DN, "tibia": 0},   "R2": {"coxa": B_R_PUSH,  "femur": DN, "tibia": 0},   "L3": {"coxa": B_L_PUSH,  "femur": DN, "tibia": 0}
        }

        # ========================================================
        # 🔄 ระบบจัดการลำดับเฟรม (Return Sequences)
        # ========================================================
        if direction == "Forward": return [fw_1, fw_2, fw_3, fw_4]
        elif direction == "Backward": return [bw_1, bw_2, bw_3, bw_4]
        
        elif direction == "Rotate Left":
            rl1 = {k: bw_1[k] if "L" in k else fw_1[k] for k in self.LEGS}
            rl2 = {k: bw_2[k] if "L" in k else fw_2[k] for k in self.LEGS}
            rl3 = {k: bw_3[k] if "L" in k else fw_3[k] for k in self.LEGS}
            rl4 = {k: bw_4[k] if "L" in k else fw_4[k] for k in self.LEGS}
            return [rl1, rl2, rl3, rl4]
            
        elif direction == "Rotate Right":
            rr1 = {k: fw_1[k] if "L" in k else bw_1[k] for k in self.LEGS}
            rr2 = {k: fw_2[k] if "L" in k else bw_2[k] for k in self.LEGS}
            rr3 = {k: fw_3[k] if "L" in k else bw_3[k] for k in self.LEGS}
            rr4 = {k: fw_4[k] if "L" in k else bw_4[k] for k in self.LEGS}
            return [rr1, rr2, rr3, rr4]

        elif direction == "StairUp":
            S_STAIR = 300; L_STAIR = -500  
            su_step1 = {"L1": {"coxa": S_STAIR, "femur": L_STAIR, "tibia": 200}, "R1": {"coxa": S_STAIR, "femur": L_STAIR, "tibia": 200}, "L2": {"coxa": -100, "femur": 0, "tibia": -100}, "R2": {"coxa": -100, "femur": 0, "tibia": -100}, "L3": {"coxa": -200, "femur": 0, "tibia": -200}, "R3": {"coxa": -200, "femur": 0, "tibia": -200}}
            su_step2 = {"L1": {"coxa": -100, "femur": -100, "tibia": 0}, "R1": {"coxa": -100, "femur": -100, "tibia": 0}, "L2": {"coxa": 0, "femur": 0, "tibia": 0}, "R2": {"coxa": 0, "femur": 0, "tibia": 0}, "L3": {"coxa": 0, "femur": 0, "tibia": 0}, "R3": {"coxa": 0, "femur": 0, "tibia": 0}}
            return [su_step1, su_step2, reset]

        elif direction == "StairDown":
            S_DOWN = 200; L_DOWN = 450 
            sd_step1 = {"L1": {"coxa": S_DOWN, "femur": L_DOWN, "tibia": 200}, "R1": {"coxa": S_DOWN, "femur": L_DOWN, "tibia": 200}, "L2": {"coxa": 0, "femur": 0, "tibia": 0}, "R2": {"coxa": 0, "femur": 0, "tibia": 0}, "L3": {"coxa": 0, "femur": 0, "tibia": 0}, "R3": {"coxa": 0, "femur": 0, "tibia": 0}}
            return [sd_step1, reset]

        elif direction == "HighStep":
            L_FWD = 200; L_MID = 0; L_BWD = -200  
            R_FWD = -200; R_MID = 0; R_BWD = 200  
            L_UP_F = -550; L_DN_F = 150  
            R_UP_F = 550;  R_DN_F = -150 
            L_UP_T = 100;  L_DN_T = -100 
            R_UP_T = -100; R_DN_T = 100  

            hs_step1 = {"L1": {"coxa": L_FWD, "femur": L_UP_F, "tibia": L_UP_T}, "R3": {"coxa": R_FWD, "femur": R_UP_F, "tibia": R_UP_T}, "L2": {"coxa": L_BWD, "femur": L_DN_F, "tibia": L_DN_T}, "R1": {"coxa": R_BWD, "femur": R_DN_F, "tibia": R_DN_T}, "L3": {"coxa": L_MID, "femur": L_DN_F, "tibia": L_DN_T}, "R2": {"coxa": R_MID, "femur": R_DN_F, "tibia": R_DN_T}}
            hs_step2 = {"L1": {"coxa": L_FWD, "femur": L_DN_F, "tibia": L_DN_T}, "R3": {"coxa": R_FWD, "femur": R_DN_F, "tibia": R_DN_T}, "L2": {"coxa": L_BWD, "femur": L_DN_F, "tibia": L_DN_T}, "R1": {"coxa": R_BWD, "femur": R_DN_F, "tibia": R_DN_T}, "L3": {"coxa": L_MID, "femur": L_DN_F, "tibia": L_DN_T}, "R2": {"coxa": R_MID, "femur": R_DN_F, "tibia": R_DN_T}}
            hs_step3 = {"L2": {"coxa": L_FWD, "femur": L_UP_F, "tibia": L_UP_T}, "R1": {"coxa": R_FWD, "femur": R_UP_F, "tibia": R_UP_T}, "L3": {"coxa": L_BWD, "femur": L_DN_F, "tibia": L_DN_T}, "R2": {"coxa": R_BWD, "femur": R_DN_F, "tibia": R_DN_T}, "L1": {"coxa": L_MID, "femur": L_DN_F, "tibia": L_DN_T}, "R3": {"coxa": R_MID, "femur": R_DN_F, "tibia": R_DN_T}}
            hs_step4 = {"L2": {"coxa": L_FWD, "femur": L_DN_F, "tibia": L_DN_T}, "R1": {"coxa": R_FWD, "femur": R_DN_F, "tibia": R_DN_T}, "L3": {"coxa": L_BWD, "femur": L_DN_F, "tibia": L_DN_T}, "R2": {"coxa": R_BWD, "femur": R_DN_F, "tibia": R_DN_T}, "L1": {"coxa": L_MID, "femur": L_DN_F, "tibia": L_DN_T}, "R3": {"coxa": R_MID, "femur": R_DN_F, "tibia": R_DN_T}}
            hs_step5 = {"L3": {"coxa": L_FWD, "femur": L_UP_F, "tibia": L_UP_T}, "R2": {"coxa": R_FWD, "femur": R_UP_F, "tibia": R_UP_T}, "L1": {"coxa": L_BWD, "femur": L_DN_F, "tibia": L_DN_T}, "R3": {"coxa": R_BWD, "femur": R_DN_F, "tibia": R_DN_T}, "L2": {"coxa": L_MID, "femur": L_DN_F, "tibia": L_DN_T}, "R1": {"coxa": R_MID, "femur": R_DN_F, "tibia": R_DN_T}}
            hs_step6 = {"L3": {"coxa": L_FWD, "femur": L_DN_F, "tibia": L_DN_T}, "R2": {"coxa": R_FWD, "femur": R_DN_F, "tibia": R_DN_T}, "L1": {"coxa": L_BWD, "femur": L_DN_F, "tibia": L_DN_T}, "R3": {"coxa": R_BWD, "femur": R_DN_F, "tibia": R_DN_T}, "L2": {"coxa": L_MID, "femur": L_DN_F, "tibia": L_DN_T}, "R1": {"coxa": R_MID, "femur": R_DN_F, "tibia": R_DN_T}}
            
            return [hs_step1, hs_step2, hs_step3, hs_step4, hs_step5, hs_step6]

        elif direction == "Turn Left": 
            REACH = -200; PULL  = 200; LIFT  = -200
            cl1 = {"L1": {"coxa": 0, "femur": LIFT, "tibia": PULL}, "R2": {"coxa": 0, "femur": LIFT, "tibia": REACH}, "L3": {"coxa": 0, "femur": LIFT, "tibia": PULL}, "R1": {"coxa": 0, "femur": 0, "tibia": PULL}, "L2": {"coxa": 0, "femur": 0, "tibia": REACH}, "R3": {"coxa": 0, "femur": 0, "tibia": PULL}}
            cl2 = {"L1": {"coxa": 0, "femur": 0, "tibia": PULL}, "R2": {"coxa": 0, "femur": 0, "tibia": REACH}, "L3": {"coxa": 0, "femur": 0, "tibia": PULL}, "R1": {"coxa": 0, "femur": 0, "tibia": PULL}, "L2": {"coxa": 0, "femur": 0, "tibia": REACH}, "R3": {"coxa": 0, "femur": 0, "tibia": PULL}}
            cl4 = {"L1": {"coxa": 0, "femur": 0, "tibia": REACH}, "R2": {"coxa": 0, "femur": 0, "tibia": PULL}, "L3": {"coxa": 0, "femur": 0, "tibia": REACH}, "R1": {"coxa": 0, "femur": LIFT, "tibia": REACH}, "L2": {"coxa": 0, "femur": LIFT, "tibia": PULL}, "R3": {"coxa": 0, "femur": LIFT, "tibia": REACH}}
            cl5 = {"L1": {"coxa": 0, "femur": 0, "tibia": REACH}, "R2": {"coxa": 0, "femur": 0, "tibia": PULL}, "L3": {"coxa": 0, "femur": 0, "tibia": REACH}, "R1": {"coxa": 0, "femur": 0, "tibia": REACH}, "L2": {"coxa": 0, "femur": 0, "tibia": PULL}, "R3": {"coxa": 0, "femur": 0, "tibia": REACH}}
            return [cl1, cl2, reset, cl4, cl5, reset]

        elif direction == "Turn Right": 
            REACH = -200; PULL  = 200; LIFT  = -200
            cr1 = {"L1": {"coxa": 0, "femur": LIFT, "tibia": REACH}, "R2": {"coxa": 0, "femur": LIFT, "tibia": PULL}, "L3": {"coxa": 0, "femur": LIFT, "tibia": REACH}, "R1": {"coxa": 0, "femur": 0, "tibia": REACH}, "L2": {"coxa": 0, "femur": 0, "tibia": PULL}, "R3": {"coxa": 0, "femur": 0, "tibia": REACH}}
            cr2 = {"L1": {"coxa": 0, "femur": 0, "tibia": REACH}, "R2": {"coxa": 0, "femur": 0, "tibia": PULL}, "L3": {"coxa": 0, "femur": 0, "tibia": REACH}, "R1": {"coxa": 0, "femur": 0, "tibia": REACH}, "L2": {"coxa": 0, "femur": 0, "tibia": PULL}, "R3": {"coxa": 0, "femur": 0, "tibia": REACH}}
            cr4 = {"L1": {"coxa": 0, "femur": 0, "tibia": PULL}, "R2": {"coxa": 0, "femur": 0, "tibia": REACH}, "L3": {"coxa": 0, "femur": 0, "tibia": PULL}, "R1": {"coxa": 0, "femur": LIFT, "tibia": PULL}, "L2": {"coxa": 0, "femur": LIFT, "tibia": REACH}, "R3": {"coxa": 0, "femur": LIFT, "tibia": PULL}}
            cr5 = {"L1": {"coxa": 0, "femur": 0, "tibia": PULL}, "R2": {"coxa": 0, "femur": 0, "tibia": REACH}, "L3": {"coxa": 0, "femur": 0, "tibia": PULL}, "R1": {"coxa": 0, "femur": 0, "tibia": PULL}, "L2": {"coxa": 0, "femur": 0, "tibia": REACH}, "R3": {"coxa": 0, "femur": 0, "tibia": PULL}}
            return [cr1, cr2, reset, cr4, cr5, reset]
        
        return None

    def handle_height(self, data):
        if not self.is_connected: return
        current_time = time.time()
        if current_time - self.last_sent_time < self.send_interval: return 
        self.last_sent_time = current_time
        
        try:
            # รับค่าองศาจาก Slider (ค่ากลางคือ 90)
            degree = int(data[0]) if isinstance(data, (tuple, list)) else int(data)
            move_time = 250 
            cmd = ""
            
            # คำนวณระยะห่างจากจุดกลาง
            offset = (degree - 90) * 5.5 
            
            for leg_key, pins in self.LEGS.items():
                f_base = 1500 # ฐาน 1500 ตามที่คุณต้องการ
                
                # --- สลับเครื่องหมายตามที่คุณแจ้งมา ---
                if leg_key.startswith("R"):
                    # ฝั่งขวา: เปลี่ยนเป็น ลบ (-) เพื่อให้สัมพันธ์กับการลุกขึ้น
                    femur_pwm = f_base - offset 
                else:
                    # ฝั่งซ้าย: เปลี่ยนเป็น บวก (+) เพื่อให้สัมพันธ์กับการลุกขึ้น
                    femur_pwm = f_base + offset 

                # บันทึกค่าลงหน่วยความจำ (เพื่อใช้ตอนหยุดเดิน)
                self.height_offsets[leg_key]["femur"] = femur_pwm - f_base
                self.height_offsets[leg_key]["tibia"] = 0

                # คุมลิมิตความปลอดภัย 500-2000
                pwm_f = max(500, min(2000, int(femur_pwm)))
                pwm_t = max(500, min(2000, int(1500))) # Tibia ล็อคไว้ที่ 1500
                
                cmd += f"#{pins['femur']}P{pwm_f} #{pins['tibia']}P{pwm_t} "
            
            self.send_command(cmd + f"T{move_time}") 
            
        except Exception as e: 
            print(f"Height Error: {e}")

    def handle_action(self, data):
        if data == "Stand":
            cmd = ""
            for leg_key, leg in self.LEGS.items():
                # ขาขวาต้องยืนที่ 1000 ขาซ้ายยืนที่ 1500 ถึงจะสูงเท่ากันพอดี
                f_stand = 1500 if leg_key.startswith("R") else 1500
                cmd += f"#{leg['coxa']}P1500 #{leg['femur']}P{f_stand} #{leg['tibia']}P1500 "
            
            self.height_offsets = {k: {"femur": 0, "tibia": 0} for k in self.LEGS}
            self.send_command(cmd + "T1500")
        elif data == "Sit":
            degree = 45; offset = (degree - 90) * 11.11 
            cmd = ""
            for leg_key, pins in self.LEGS.items():
                femur_id = pins["femur"]; coxa_id = pins["coxa"]; tibia_id = pins["tibia"]
                if femur_id in self.INVERTED_FEMUR: femur_pwm = int(1500 + offset)
                else: femur_pwm = int(1500 - offset)
                tibia_val = 1875 if leg_key.startswith("R") else 1150 
                cmd += f"#{coxa_id}P1500 #{femur_id}P{femur_pwm} #{tibia_id}P{tibia_val} "
                
            self.height_offsets = {k: {"femur": 0, "tibia": 0} for k in self.LEGS}
            self.send_command(cmd + "T2000")

    def handle_camera_servo(self, type_cmd, channel, value):
        if type_cmd == "SERVO": self.send_command(f"#{channel}P{int(value)}T200")

    def toggle_connection(self, port, baud):
        if not self.is_connected:
            try:
                self.ser = serial.Serial(port, int(baud), timeout=1)
                self.is_connected = True
                self.update_status()
                self.control_ui.set_connect_status(True); self.camera_ui.set_enabled(True) 
                messagebox.showinfo("Success", f"Connected to {port}")
            except Exception as e: messagebox.showerror("Error", f"Connection Failed: {e}")
        else:
            if self.ser and self.ser.is_open: self.ser.close()
            self.is_connected = False; self.ser = None
            self.control_ui.set_connect_status(False); self.camera_ui.set_enabled(False)

    def toggle_camera(self):
        if not self.is_camera_open:
            self.camera_ui.start_camera_stream()
            self.is_camera_open = True; self.control_ui.set_camera_status(True)
        else:
            self.camera_ui.stop_camera_stream()
            self.is_camera_open = False; self.control_ui.set_camera_status(False)

    def send_command(self, cmd_string):
        if self.is_connected and self.ser:
            try: 
                # พิมพ์ดูค่าที่ส่งไปจริงใน Console เพื่อใช้ตรวจสอบว่าโปรแกรมส่งค่าออกไปหรือไม่
                print(f"➡️ SENDING: {cmd_string}")
                self.ser.write((cmd_string + "\r\n").encode('utf-8'))
            except OSError as e: 
                # ถ้าส่งข้อมูลไม่ได้ (เช่น บอร์ดดับ, สายหลุด) ให้ตัดการเชื่อมต่อทันที
                print(f"Hardware Disconnected: {e}")
                self.stop_event.set()  # สั่งหยุด Thread การเดิน
                self.is_connected = False
                if self.ser: 
                    self.ser.close()
                    self.ser = None
                
                # อัปเดต UI กลับเป็นสถานะออฟไลน์
                self.root.after(0, self.update_status)
                self.root.after(0, lambda: self.control_ui.set_connect_status(False))
                self.root.after(0, lambda: self.camera_ui.set_enabled(False))
                
                # แจ้งเตือนผู้ใช้
                self.root.after(0, lambda: messagebox.showerror(
                    "Connection Lost", 
                    "บอร์ดควบคุมตัดการเชื่อมต่อกะทันหัน!\n(สาเหตุหลัก: แบตเตอรี่จ่ายไฟไม่ทันจนบอร์ดดับ หรือ สาย USB หลวม)"
                ))
            except Exception as e:
                print(f"Send Error: {e}")

    def set_speed(self, mode):
        self.speed_mode = mode
        self.update_status()
        self.btn_slow.config(bg="#f0f0f0", fg="black", relief="raised")
        self.btn_norm.config(bg="#f0f0f0", fg="black", relief="raised")
        self.btn_fast.config(bg="#f0f0f0", fg="black", relief="raised")
        
        if mode == "Slow": self.btn_slow.config(bg="#FFEB3B", fg="black", relief="sunken")
        elif mode == "Normal": self.btn_norm.config(bg="#81C784", fg="white", relief="sunken")
        elif mode == "Fast": self.btn_fast.config(bg="#E57373", fg="white", relief="sunken")

    def _create_speed_controls(self, parent_frame):
        speed_frame = tk.Frame(parent_frame, bg="#333")
        speed_frame.pack(side="right", padx=10)

        tk.Label(speed_frame, text="SPEED:", bg="#333", fg="white", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 5))

        self.btn_slow = tk.Button(speed_frame, text="SLOW", width=8, font=("Arial", 8, "bold"), command=lambda: self.set_speed("Slow"))
        self.btn_slow.pack(side="left", padx=2, pady=5)
        self.btn_norm = tk.Button(speed_frame, text="NORMAL", width=8, font=("Arial", 8, "bold"), command=lambda: self.set_speed("Normal"))
        self.btn_norm.pack(side="left", padx=2, pady=5)
        self.btn_fast = tk.Button(speed_frame, text="FAST", width=8, font=("Arial", 8, "bold"), command=lambda: self.set_speed("Fast"))
        self.btn_fast.pack(side="left", padx=2, pady=5)

        self.speed_canvas = tk.Canvas(speed_frame, width=90, height=12, bg="#555", highlightthickness=0)
        self.speed_canvas.pack(side="left", padx=10)
        self.speed_bar = self.speed_canvas.create_rectangle(0, 0, 0, 12, fill="#81C784")
        self.set_speed("Normal")

    def update_status(self, current_action="Ready"):
        conn_text = "Online" if self.is_connected else "Offline"
        status_text = f" Status: {current_action} | Connection: {conn_text} | Mode: {self.walk_mode} "
        self.status_bar.config(text=status_text)
        
        if self.is_connected: self.status_bar.config(fg="#4CAF50") 
        else: self.status_bar.config(fg="#f44336")
        
        if hasattr(self, 'speed_canvas'):
            if self.speed_mode == "Slow":
                self.speed_canvas.coords(self.speed_bar, 0, 0, 30, 12)
                self.speed_canvas.itemconfig(self.speed_bar, fill="#FFEB3B")
            elif self.speed_mode == "Normal":
                self.speed_canvas.coords(self.speed_bar, 0, 0, 60, 12)
                self.speed_canvas.itemconfig(self.speed_bar, fill="#81C784")
            elif self.speed_mode == "Fast":
                self.speed_canvas.coords(self.speed_bar, 0, 0, 90, 12)
                self.speed_canvas.itemconfig(self.speed_bar, fill="#E57373")

if __name__ == "__main__":
    root = tk.Tk()
    app = RobotControllerApp(root)
    root.mainloop()