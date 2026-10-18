import sqlite3
import math
from datetime import datetime
import cv2
import os
import time
import threading
import serial
from adafruit_pn532.uart import PN532_UART
import easyocr
import numpy as np
from PIL import Image, ImageFont, ImageDraw

class ParkingSys:
    def __init__(self, db_name='parking.db'):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.camera = CameraStream(0)
        self.alpr_reader = easyocr.Reader(['th', 'en'], gpu=True)

    def __del__(self):
        self.conn.close()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS members (
                uid TEXT PRIMARY KEY,
                license_plate TEXT,
                member_type TEXT DEFAULT 'regular',
                registered_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS parking_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT,
                time_in TIMESTAMP,
                time_out TIMESTAMP,
                status TEXT DEFAULT 'parked',
                fee_calculated REAL DEFAULT 0.0,
                image_path TEXT, 
                FOREIGN KEY (uid) REFERENCES members(uid)
            )
        ''')
        self.conn.commit()
        print("Table created")

    def create_member(self, uid, license_plate, member_type='regular'):
        try:
            self.cursor.execute('''
                INSERT INTO members (uid, license_plate, member_type)
                VALUES (?, ?, ?)
            ''', (uid, license_plate, member_type))
            self.conn.commit()
            return True, f"Add member license plate {license_plate} success"
        except sqlite3.IntegrityError:
            return False, f"[Error] UID {uid} already added"
        except Exception as e:
            return False, f"[Error] {e}"

    def read_all_members(self):
        try:
            self.cursor.execute("SELECT uid, license_plate, member_type, registered_date FROM members")
            return self.cursor.fetchall()
        except Exception as e:
            print(f"[ERROR] Database read error: {e}")
            return []

    def update_member(self, target_uid, new_plate, new_type):
        try:
            self.cursor.execute('''
                UPDATE members
                SET license_plate = ?, member_type = ?
                WHERE uid = ?
            ''', (new_plate, new_type, target_uid))
            self.conn.commit()

            if self.cursor.rowcount > 0:
                return True, f"Update UID {target_uid} success"
            else:
                return False, f"No UID {target_uid} found"
        except Exception as e:
            return False, f"[Error] {e}"

    def delete_member(self, target_uid):
        try:
            self.cursor.execute("DELETE FROM parking_logs WHERE uid = ?", (target_uid,))

            self.cursor.execute("DELETE FROM members WHERE uid = ?", (target_uid,))
            self.conn.commit()

            if self.cursor.rowcount > 0:
                return True, f"Delete UID {target_uid} success"
            else:
                return False, f"No UID {target_uid} found"
        except Exception as e:
            return False, f"[Error] {e}"    

    def register_member(self, uid, license_plate, member_type='regular'):
        try:
            self.cursor.execute('''
                INSERT INTO members (uid, license_plate, member_type)
                VALUES (?, ?, ?)
            ''', (uid, license_plate, member_type))
            self.conn.commit()
            print(f"Registered: UID {uid} | Plate: {license_plate}")
        except sqlite3.IntegrityError:
            print(f"Cannot register: UID {uid} already exists.")

    def _get_active_session(self, uid):
        self.cursor.execute('''
            SELECT log_id FROM parking_logs
            WHERE uid = ? AND status = 'parked'
        ''', (uid,))

        result = self.cursor.fetchone()

        if result:
            return result[0]
        else:
            return None

    def _process_entry(self, uid, license_plate):
        frame = self.camera.read()
        if frame is None:
            return "Camera is not ready"

        height, width, _ = frame.shape
        y_start = int(height * 0.4)
        y_end = int(height * 0.9)
        x_start = int(width * 0.2)
        x_end = int(width * 0.8)

        roi_frame = frame[y_start:y_end, x_start:x_end]
        gray_roi = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        blur_roi = cv2.GaussianBlur(gray_roi, (5, 5), 0)
        _, thresh_roi = cv2.threshold(blur_roi, 100, 255, cv2.THRESH_BINARY)
        
        detected_texts = self.alpr_reader.readtext(thresh_roi, detail=0)

        clean_db_plate = license_plate.replace("-", "").replace(" ", "")
        alpr_combined = "".join(detected_texts).replace("-", "").replace(" ", "")
        alpr_raw_text = " ".join(detected_texts) # เก็บข้อความดิบไว้โชว์บนหน้าจอ

        if clean_db_plate not in alpr_combined:
            cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), (0, 0, 255), 2)
            
            return (f"[DENIED] Access denied\n"
                    f"License not found or not registered\n"
                    f"In system: {license_plate} | Read found: '{alpr_raw_text}'")
        
        cv2.rectangle(frame, (x_start, y_start), (x_end, y_end), (0, 255, 0), 2)
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        self.cursor.execute('''
            INSERT INTO parking_logs (uid, time_in, status)
            VALUES (?, ?, 'parked')
        ''', (uid, now))
        self.conn.commit()

        log_id = self.cursor.lastrowid
        
        #Save image
        img_path = self._save_image_with_overlay(frame, log_id, license_plate)
        if img_path:
            self.cursor.execute('UPDATE parking_logs SET image_path = ? WHERE log_id = ?', (img_path, log_id))
            self.conn.commit()

        return (f"[ENTRY]\n"
                f"License detect: {license_plate}\n"
                f"Time: {now}")

    def _process_exit(self, log_id):
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        self.cursor.execute('''
            SELECT time_in FROM parking_logs 
            WHERE log_id = ?
        ''', (log_id,))
        time_in_str = self.cursor.fetchone()[0]

        fee, actual_hours = self._calculate_fee(time_in_str, now_str)
        self.cursor.execute('''
            UPDATE parking_logs 
            SET time_out = ?, status = 'completed', fee_calculated = ?
            WHERE log_id = ?
        ''', (now_str, fee, log_id))

        self.conn.commit()
        return (f"[Exit] Time: {now_str}\n"
                f"Actual hour(s): {actual_hours:.2f} Hour(s)\n"
                f"Fee: {fee} Baht")

    def handle_scan(self, uid):
        print(f"\n Scan card, UID: {uid}")

        self.cursor.execute('SELECT license_plate FROM members WHERE uid = ?', (uid,))
        member = self.cursor.fetchone()

        if not member:
            return f"[Error] Access denied: UID not found {uid}"

        active_log_id = self._get_active_session(uid)

        if active_log_id is None:
            result_msg = self._process_entry(uid,member[0])
        else:
            result_msg = self._process_exit(active_log_id)

        return result_msg

    def _calculate_fee(self, time_in_str, time_out_str):
        format_str = '%Y-%m-%d %H:%M:%S'
        time_in = datetime.strptime(time_in_str, format_str)
        time_out = datetime.strptime(time_out_str, format_str)

        time_diff = time_out - time_in
        hours_parked = time_diff.total_seconds() / 3600
        billable_hours = math.ceil(hours_parked)
        fee = billable_hours *20

        return fee, hours_parked

    #camera
    def _capture_car_image(self, frame, log_id, license_plate):
        if not os.path.exists("parking_images"):
            os.makedirs("parking_images")

        frame_copy = frame.copy()
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        text = f"{license_plate} | {timestamp}"

        # วาดข้อความทับลงไป
        cv2.putText(frame_copy, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 255, 0), 2, cv2.LINE_AA)

        filename = f"parking_images/entry_{log_id}.jpg"
        cv2.imwrite(filename, frame_copy)
        
        return filename

    def close(self):
        self.camera.stop()
        self.conn.close()

    def _save_image_with_overlay(self, frame, log_id, license_plate):
        if not os.path.exists("parking_images"):
            os.makedirs("parking_images")

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        text = f"{license_plate} | {timestamp}"

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_im = Image.fromarray(frame_rgb)
        draw = ImageDraw.Draw(pil_im)

        # (For Mac/Linux use other font Ex: "Sarabun-Regular.ttf")
        try:
            font = ImageFont.truetype("tahoma.ttf", 30)
        except IOError:
            font = ImageFont.load_default()
            print("No Tahoma font found")

        draw.text((10, 30), text, font=font, fill=(0, 255, 0))
        frame_with_text = cv2.cvtColor(np.array(pil_im), cv2.COLOR_RGB2BGR)
        filename = f"parking_images/entry_{log_id}.jpg"
        cv2.imwrite(filename, frame_with_text)
        
        return filename



#camera class
class CameraStream:
    def __init__(self, src=0):
        self.stream = cv2.VideoCapture(src)
        self.ret, self.frame = self.stream.read()
        self.stopped = False

        if self.stream.isOpened():
            print("Camera standby")
            threading.Thread(target=self.update, args=(), daemon=True).start()
        else:
            print("Camera not opened")

    def update(self):
        while True:
            if self.stopped:
                return
            self.ret, self.frame = self.stream.read()
            time.sleep(0.03)

    def read(self):
        return self.frame

    def stop(self):
        self.stopped = True
        self.stream.release()

'''
def start_nfc_reader(com_port, parking_system):
    print(f"Connect to PN532, port:{com_port}")
    try:
        uart = serial.Serial(com_port, baudrate=115200, timeout=1)
        pn532 = PN532_UART(uart, debug=False)
        ic, ver, rev, support = pn532.firmware_version
        print(f"Found reader: {ver}.{rev}")
        pn532.SAM_configuration()
        print("Waiting for NFC")
    except Exception as e:
        print(f"Error: {e}")
        return

    while True:
        try:
            uid_bytes = pn532.read_passive_target(timeout=0.5)
            if uid_bytes is not None:
                uid_hex = uid_bytes.hex().upper()
                print(f"\nNFC found: {uid_hex}")
                
                
                parking_system.handle_scan(uid_hex)
                
                time.sleep(2)
                print("\nWaiting for NFC")
        except Exception as e:
            time.sleep(1)
'''

if __name__ == "__main__":
    parking = ParkingSys('parking.db')
    parking.create_tables()
    
    parking.register_member('A1B2C3D4', 'กท-2058')
    uid_from_nfc = 'A1B2C3D4'
    parking.handle_scan(uid_from_nfc)