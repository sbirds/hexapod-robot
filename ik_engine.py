import math

# ==========================================
# [ส่วนที่ 1] ตั้งค่าขนาดหุ่นยนต์ (Unit: mm)
# ==========================================
HIP_OFFSET_X = 74   
HIP_OFFSET_Y = 39   

COXA_LENGTH = 28    
FEMUR_LENGTH = 84   
TIBIA_LENGTH = 127  

HOME_X = 150
HOME_Y_FB = 123
HOME_Y_M = 177

RAD2DEG = 180.0 / math.pi

# ==============================================================================
# [ส่วนที่ 2] FINE TUNING (จูนละเอียด)
# ตอนนี้ตั้งศูนย์ที่ 1500 แล้ว ค่าตรงนี้ควรเป็น 0 หรือใส่นิดหน่อยถ้าเบี้ยว
# ==============================================================================
LEG_OFFSETS = {
    "L1": {"coxa": 0, "femur": 0, "tibia": 0}, 
    "L2": {"coxa": 0, "femur": 0, "tibia": 0}, 
    "L3": {"coxa": 0, "femur": 0, "tibia": 0},
    "R1": {"coxa": 0, "femur": 0, "tibia": 0},
    "R2": {"coxa": 0, "femur": 0, "tibia": 0},
    "R3": {"coxa": 0, "femur": 0, "tibia": 0},
}

class Position:
    def __init__(self, x=0, y=0, z=0):
        self.x = x; self.y = y; self.z = z

class LegIK:
    def __init__(self, name, mount_x, mount_y, pins, inverted_list, coxa_dir):
        self.name = name
        self.mount_x = mount_x
        self.mount_y = mount_y
        self.pins = pins
        self.is_left_side = (pins['femur'] in inverted_list) 
        self.coxa_direction = coxa_dir
        self.mount_angle_rad = math.atan2(mount_y, mount_x)
        self.offsets = LEG_OFFSETS.get(name, {"coxa": 0, "femur": 0, "tibia": 0})

    def solve_ik(self, target_x, target_y, target_z):
        # 1. Coordinate Transform
        lx = target_x - self.mount_x
        ly = target_y - self.mount_y
        lz = target_z

        # 2. Coxa
        v = math.atan2(ly, lx) - self.mount_angle_rad
        while v > math.pi: v -= 2*math.pi
        while v < -math.pi: v += 2*math.pi
        coxa_deg = math.degrees(v)

        # 3. Femur/Tibia
        true_x = math.sqrt(lx**2 + ly**2) - COXA_LENGTH
        d = math.sqrt(true_x**2 + lz**2)
        if d > (FEMUR_LENGTH + TIBIA_LENGTH): d = FEMUR_LENGTH + TIBIA_LENGTH 

        try:
            alpha_rad = math.acos((FEMUR_LENGTH**2 + d**2 - TIBIA_LENGTH**2) / (2 * FEMUR_LENGTH * d)) + math.atan2(lz, true_x)
            beta_rad = math.acos((FEMUR_LENGTH**2 + TIBIA_LENGTH**2 - d**2) / (2 * FEMUR_LENGTH * TIBIA_LENGTH))
        except ValueError:
            return None 

        femur_deg = math.degrees(alpha_rad)
        tibia_deg = math.degrees(beta_rad)
        
        deg_to_pwm = 11.111 

        # =================================================================
        # CALCULATE PWM (Standard 1500 Base) - แก้ไขแล้ว!
        # =================================================================

        # --- COXA ---
        base_coxa = 1500 + (coxa_deg * self.coxa_direction * deg_to_pwm)
        coxa_pwm = base_coxa + self.offsets['coxa']

        # --- FEMUR ---
        if self.is_left_side:
            # ฝั่งซ้าย: ยกขึ้นต้องบวก (+)
            base_femur = 1500 + (femur_deg * deg_to_pwm)
        else:
            # ฝั่งขวา: ยกขึ้นต้องลบ (-)
            base_femur = 1100 - (femur_deg * deg_to_pwm)
            
        femur_pwm = base_femur + self.offsets['femur']

        # --- TIBIA ---
        tibia_servo_angle = tibia_deg - 90 
        if self.is_left_side:
            # ฝั่งซ้าย: งอขาต้องบวก (+)
            base_tibia = 1500 + (tibia_servo_angle * deg_to_pwm)
        else:
            # ฝั่งขวา: งอขาต้องลบ (-)
            base_tibia = 1500 - (tibia_servo_angle * deg_to_pwm)
            
        tibia_pwm = base_tibia + self.offsets['tibia']

        # =================================================================
        # [จุดที่เพิ่มเข้าไป] SOFTWARE BUMP-STOP ป้องกันมอเตอร์หมุนทะลุ 1500
        # =================================================================
        SAFE_MIN = 500
        SAFE_MAX = 2000

        coxa_pwm = max(SAFE_MIN, min(SAFE_MAX, coxa_pwm))
        femur_pwm = max(SAFE_MIN, min(SAFE_MAX, femur_pwm))
        tibia_pwm = max(SAFE_MIN, min(SAFE_MAX, tibia_pwm))

        return {
            self.pins['coxa']: int(coxa_pwm),
            self.pins['femur']: int(femur_pwm),
            self.pins['tibia']: int(tibia_pwm)
        }

class HexapodIK:
    def __init__(self, legs_mapping, inverted_femur_list, coxa_dir_dict):
        self.legs = []
        mount_points = {
            "L1": (HIP_OFFSET_X, HIP_OFFSET_Y), "L2": (0, HIP_OFFSET_Y + 25), "L3": (-HIP_OFFSET_X, HIP_OFFSET_Y),
            "R1": (HIP_OFFSET_X, -HIP_OFFSET_Y), "R2": (0, -(HIP_OFFSET_Y + 25)), "R3": (-HIP_OFFSET_X, -HIP_OFFSET_Y)
        }
        for name, pins in legs_mapping.items():
            mx, my = mount_points.get(name, (0,0))
            c_dir = coxa_dir_dict.get(name, 1)
            leg = LegIK(name, mx, my, pins, inverted_femur_list, c_dir)
            self.legs.append(leg)

    def calculate_stand_posture(self, z_height=-60):
        commands = ""
        for leg in self.legs:
            tx, ty = 0, 0
            if "L" in leg.name:
                if "1" in leg.name: tx, ty = HOME_X, HOME_Y_FB
                elif "2" in leg.name: tx, ty = 0, HOME_Y_M
                elif "3" in leg.name: tx, ty = -HOME_X, HOME_Y_FB
            else:
                if "1" in leg.name: tx, ty = HOME_X, -HOME_Y_FB
                elif "2" in leg.name: tx, ty = 0, -HOME_Y_M
                elif "3" in leg.name: tx, ty = -HOME_X, -HOME_Y_FB

            pwm_values = leg.solve_ik(tx, ty, z_height)
            if pwm_values:
                for pin, pwm in pwm_values.items():
                    pwm = max(500, min(1500, pwm)) 
                    commands += f"#{pin}P{pwm} "
        return commands