import sys
import os
import time
import json
import base64
import datetime
import csv
import paho.mqtt.client as mqtt
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QFormLayout, QLineEdit, QTableWidget, QHeaderView,
                             QTableWidgetItem, QTabWidget, QFileDialog, QComboBox)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from parkSysDemo import ParkingSys


class MQTTListenerThread(QThread):
    card_scanned = pyqtSignal(str)
    status_requested = pyqtSignal(str)
    gate_exit_requested = pyqtSignal(str, float)
    search_requested = pyqtSignal(str, str)
    log_msg = pyqtSignal(str)

    def __init__(self, broker_address="broker.emqx.io"):
        super().__init__()
        self.broker = broker_address
        self.client = mqtt.Client()
        self.is_running = True

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.log_msg.emit(f"Connected to MQTT Broker: {self.broker} successfully")
            self.client.subscribe("parking/entry/scan")
            self.client.subscribe("parking/request/status")
            self.client.subscribe("parking/gate/exit")
            self.client.subscribe("parking/search/request")
        else:
            self.log_msg.emit(f"Failed to connect to MQTT (code: {rc})")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8")

        if topic == "parking/entry/scan":
            self.card_scanned.emit(payload)
        elif topic == "parking/request/status":
            try:
                data = json.loads(payload)
                uid = data.get("uid")
                if uid:
                    self.status_requested.emit(uid)
            except Exception:
                pass
        elif topic == "parking/gate/exit":
            try:
                data = json.loads(payload)
                uid = data.get("uid")
                amount = float(data.get("amount", 20.0))
                if uid:
                    self.gate_exit_requested.emit(uid, amount)
            except Exception as e:
                self.log_msg.emit(f"Exit payload parse error: {e}")
        elif topic == "parking/search/request":
            try:
                data = json.loads(payload)
                query = data.get("query", "")
                request_id = data.get("requestId", "")
                if query and request_id:
                    self.search_requested.emit(query, request_id)
            except Exception as e:
                self.log_msg.emit(f"Search parse error: {e}")

    def run(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        self.log_msg.emit(f"Connecting to MQTT Broker: {self.broker}...")
        try:
            self.client.connect(self.broker, 1883, 60)
            self.client.loop_start()
            
            while self.is_running:
                self.msleep(100)
                
        except Exception as e:
            self.log_msg.emit(f"[Error] MQTT: {e}")

    def stop(self):
        self.is_running = False
        self.client.loop_stop()
        self.client.disconnect()
        self.wait()


class ParkingDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.parking = ParkingSys('parking.db')
        self.parking.create_tables()

        self.parking.register_member('A1B2C3D4', 'BKK-1234')
        self.parking.register_member('E5F6G7H8', 'SK-9999', 'vip')

        # Parking Lot Capacity Settings
        self.total_capacity = 50

        self.is_reading_ntag = False

        self.pub_client = mqtt.Client()
        try:
            self.pub_client.connect("broker.emqx.io", 1883, 60)
            self.pub_client.loop_start()
        except Exception as e:
            print(f"MQTT Pub Connect Error: {e}")

        self.setWindowTitle("SMART PARKING TERMINAL")
        self.resize(1150, 700)

        self.setStyleSheet("""
            QMainWindow, QWidget#tab_bg { background-color: #1E1E2E; }
            QLabel { color: #CDD6F4; }
            QTextEdit, QLineEdit, QTableWidget, QComboBox {
                background-color: #181825;
                color: #A6E3A1;
                border: 1px solid #45475A;
                border-radius: 8px;
                padding: 5px;
            }
            QTableWidget { color: #CDD6F4; }
            QHeaderView::section {
                background-color: #313244;
                color: #CDD6F4;
                border: none;
                padding: 6px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #89B4FA;
                color: #11111B;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover { background-color: #B4BEFE; }
            QPushButton:pressed { background-color: #74C7EC; }
            
            QTabWidget::pane { border: 0px; }
            QTabBar::tab {
                background-color: #313244;
                color: #CDD6F4;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background-color: #181825;
                color: #F9E2AF;
                font-weight: bold;
            }
        """)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_dashboard = QWidget()
        self.tab_dashboard.setObjectName("tab_bg")
        
        self.tab_management = QWidget()
        self.tab_management.setObjectName("tab_bg")

        self.tab_logs = QWidget()
        self.tab_logs.setObjectName("tab_bg")
        
        self.tabs.addTab(self.tab_dashboard, "🎥 Live Dashboard")
        self.tabs.addTab(self.tab_management, "⚙️ Database Management")
        self.tabs.addTab(self.tab_logs, "📋 Parking Logs")

        self.setup_dashboard_tab()
        self.setup_management_tab()
        self.setup_logs_tab()
    
        self.handle_read()
        self.handle_read_logs()
        self.update_capacity_display()

        self.log_message("SYSTEM INITIALIZED. READY.")
        
        self.mqtt_thread = MQTTListenerThread(broker_address="broker.emqx.io")
        self.mqtt_thread.card_scanned.connect(self.process_scan)
        self.mqtt_thread.status_requested.connect(self.send_user_status)
        self.mqtt_thread.gate_exit_requested.connect(self.process_exit)
        self.mqtt_thread.search_requested.connect(self.process_search)
        self.mqtt_thread.log_msg.connect(self.log_message)
        self.mqtt_thread.start()

    def setup_dashboard_tab(self):
        container_layout = QVBoxLayout()

        # --- Top Capacity Status Cards ---
        capacity_layout = QHBoxLayout()

        self.card_total = QLabel("TOTAL SLOTS\n50")
        self.card_total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_total.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.card_total.setStyleSheet("""
            background-color: #313244; color: #89B4FA; 
            border-radius: 10px; padding: 10px; margin-bottom: 5px;
        """)

        self.card_parked = QLabel("OCCUPIED\n0")
        self.card_parked.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_parked.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.card_parked.setStyleSheet("""
            background-color: #313244; color: #FAB387; 
            border-radius: 10px; padding: 10px; margin-bottom: 5px;
        """)

        self.card_available = QLabel("AVAILABLE SLOTS\n50")
        self.card_available.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_available.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.card_available.setStyleSheet("""
            background-color: #A6E3A1; color: #11111B; 
            border-radius: 10px; padding: 10px; margin-bottom: 5px;
        """)

        capacity_layout.addWidget(self.card_total)
        capacity_layout.addWidget(self.card_parked)
        capacity_layout.addWidget(self.card_available)
        container_layout.addLayout(capacity_layout)

        # --- Main Live Split View ---
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()

        self.plate_label = QLabel("Waiting for user")
        self.plate_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.plate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plate_label.setStyleSheet("""
            background-color: #313244;
            color: #F38BA8;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 10px;
        """)

        self.image_display = QLabel("NO CAMERA SIGNAL")
        self.image_display.setFont(QFont("Segoe UI", 12))
        self.image_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_display.setStyleSheet("""
            background-color: #11111B;
            color: #585B70;
            border: 2px dashed #45475A;
            border-radius: 12px;
        """)
        self.image_display.setFixedSize(450, 300)

        left_layout.addWidget(self.plate_label)
        left_layout.addWidget(self.image_display)
        left_layout.addStretch()

        main_layout.addLayout(left_layout)

        right_layout = QVBoxLayout()

        title_log = QLabel("LIVE SYSTEM LOGS")
        title_log.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_log.setStyleSheet("color: #FAB387;")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))

        btn_layout = QHBoxLayout()
        btn_scan_car1 = QPushButton("Scan: BKK-1234")
        btn_scan_car1.setStyleSheet("background-color: #CBA6F7;")
        btn_scan_car1.clicked.connect(lambda: self.simulate_scan('A1B2C3D4'))

        btn_scan_car2 = QPushButton("Scan: SK-9999")
        btn_scan_car2.setStyleSheet("background-color: #CBA6F7;")
        btn_scan_car2.clicked.connect(lambda: self.simulate_scan('E5F6G7H8'))
        
        btn_layout.addWidget(btn_scan_car1)
        btn_layout.addWidget(btn_scan_car2)

        right_layout.addWidget(title_log)
        right_layout.addWidget(self.log_text)
        right_layout.addLayout(btn_layout)

        main_layout.addLayout(right_layout)
        container_layout.addLayout(main_layout)

        self.tab_dashboard.setLayout(container_layout)

    def update_capacity_display(self):
        """ Calculate & Update capacity UI cards and broadcast via MQTT """
        try:
            self.parking.cursor.execute("SELECT COUNT(*) FROM parking_logs WHERE status = 'parked'")
            parked_count = self.parking.cursor.fetchone()[0]
            available_slots = max(0, self.total_capacity - parked_count)

            self.card_total.setText(f"TOTAL CAPACITY\n{self.total_capacity} Slots")
            self.card_parked.setText(f"OCCUPIED\n{parked_count} Vehicles")
            self.card_available.setText(f"AVAILABLE SLOTS\n{available_slots} Slots")

            if available_slots == 0:
                self.card_available.setText("PARKING FULL\n0 Slots Left")
                self.card_available.setStyleSheet("""
                    background-color: #F38BA8; color: #11111B; 
                    border-radius: 10px; padding: 10px; margin-bottom: 5px; font-weight: bold;
                """)
            else:
                self.card_available.setStyleSheet("""
                    background-color: #A6E3A1; color: #11111B; 
                    border-radius: 10px; padding: 10px; margin-bottom: 5px; font-weight: bold;
                """)

            # Broadcast capacity data via MQTT
            capacity_payload = json.dumps({
                "total": self.total_capacity,
                "parked": parked_count,
                "available": available_slots,
                "is_full": available_slots == 0
            })
            self.pub_client.publish("parking/capacity/live", capacity_payload)

        except Exception as e:
            self.log_message(f"Error updating capacity: {e}")

    def setup_management_tab(self):
        layout = QHBoxLayout()
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Database Management", font=QFont("Segoe UI", 12, QFont.Weight.Bold)))
        
        form_layout = QFormLayout()

        uid_input_layout = QHBoxLayout()
        self.input_uid = QLineEdit()
        self.input_uid.setPlaceholderText("Enter UID or tap NTAG")
        
        self.btn_read_ntag = QPushButton("📡 Tap NTAG to Read UID")
        self.btn_read_ntag.setStyleSheet("background-color: #FAB387; color: #11111B;")
        self.btn_read_ntag.clicked.connect(self.toggle_ntag_read_mode)

        uid_input_layout.addWidget(self.input_uid)
        uid_input_layout.addWidget(self.btn_read_ntag)

        self.input_plate = QLineEdit()
        self.input_plate.setPlaceholderText("Enter license plate")
        self.input_type = QLineEdit()
        self.input_type.setText("regular")
        
        form_layout.addRow("UID:", uid_input_layout)
        form_layout.addRow("License Plate:", self.input_plate)
        form_layout.addRow("Member Type:", self.input_type)
        left_panel.addLayout(form_layout)
        
        btn_create = QPushButton("Add New Member")
        btn_create.clicked.connect(self.handle_create)
        btn_update = QPushButton("Update Data")
        btn_update.clicked.connect(self.handle_update)
        btn_delete = QPushButton("Delete Member")
        btn_delete.clicked.connect(self.handle_delete)
        btn_read = QPushButton("Refresh Table")
        btn_read.clicked.connect(self.handle_read)

        left_panel.addWidget(btn_create)
        left_panel.addWidget(btn_update)
        left_panel.addWidget(btn_delete)
        left_panel.addSpacing(20)
        left_panel.addWidget(btn_read)
        left_panel.addStretch() 
        
        layout.addLayout(left_panel, stretch=1)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Member List"))
        self.table_members = QTableWidget()
        self.table_members.setColumnCount(4)
        self.table_members.setHorizontalHeaderLabels(["UID", "License Plate", "Type", "Registration Date"])
        self.table_members.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_members.cellClicked.connect(self.autofill_form) 
        
        right_panel.addWidget(self.table_members)
        layout.addLayout(right_panel, stretch=2) 
        self.tab_management.setLayout(layout)

    def setup_logs_tab(self):
        layout = QVBoxLayout()

        top_layout = QHBoxLayout()
        title = QLabel("PARKING LOGS HISTORY")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #89B4FA;")

        self.input_log_search = QLineEdit()
        self.input_log_search.setPlaceholderText("Filter Plate / UID...")
        self.input_log_search.textChanged.connect(self.handle_read_logs)

        self.combo_status_filter = QComboBox()
        self.combo_status_filter.addItems(["All Status", "parked", "paid", "completed"])
        self.combo_status_filter.currentTextChanged.connect(self.handle_read_logs)

        btn_refresh_logs = QPushButton("🔄 Refresh")
        btn_refresh_logs.setFixedWidth(100)
        btn_refresh_logs.clicked.connect(self.handle_read_logs)

        btn_export_csv = QPushButton("📥 Export CSV")
        btn_export_csv.setStyleSheet("background-color: #A6E3A1; color: #11111B;")
        btn_export_csv.setFixedWidth(120)
        btn_export_csv.clicked.connect(self.handle_export_csv)

        top_layout.addWidget(title)
        top_layout.addWidget(self.input_log_search)
        top_layout.addWidget(self.combo_status_filter)
        top_layout.addWidget(btn_refresh_logs)
        top_layout.addWidget(btn_export_csv)

        self.table_logs = QTableWidget()
        self.table_logs.setColumnCount(7)
        self.table_logs.setHorizontalHeaderLabels([
            "Log ID", "UID", "License Plate", "Time In", "Time Out", "Status", "Fee (THB)"
        ])
        self.table_logs.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        layout.addLayout(top_layout)
        layout.addWidget(self.table_logs)
        self.tab_logs.setLayout(layout)

    def handle_read_logs(self):
        try:
            search_query = self.input_log_search.text().strip() if hasattr(self, 'input_log_search') else ""
            status_filter = self.combo_status_filter.currentText() if hasattr(self, 'combo_status_filter') else "All Status"

            sql = """
                SELECT 
                    l.log_id, 
                    l.uid, 
                    COALESCE(m.license_plate, 'Unregistered') AS license_plate, 
                    l.time_in, 
                    l.time_out, 
                    l.status, 
                    l.fee_calculated 
                FROM parking_logs l
                LEFT JOIN members m ON l.uid = m.uid
                WHERE 1=1
            """
            params = []

            if search_query:
                sql += " AND (l.uid LIKE ? OR m.license_plate LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            if status_filter != "All Status":
                sql += " AND l.status = ?"
                params.append(status_filter)

            sql += " ORDER BY l.log_id DESC"

            self.parking.cursor.execute(sql, params)
            logs_data = self.parking.cursor.fetchall()

            self.table_logs.setRowCount(len(logs_data))
            for row_idx, row_data in enumerate(logs_data):
                for col_idx, item_data in enumerate(row_data):
                    value = str(item_data) if item_data is not None else "-"
                    if col_idx == 6 and item_data is not None:
                        value = f"{float(item_data):.2f}"
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_logs.setItem(row_idx, col_idx, item)

            self.update_capacity_display()

        except Exception as e:
            self.log_message(f"Error reading parking logs: {e}")

    def handle_export_csv(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, 
                "Export Parking Logs to CSV", 
                "parking_logs.csv", 
                "CSV Files (*.csv);;All Files (*)"
            )
            
            if not file_path:
                return

            search_query = self.input_log_search.text().strip()
            status_filter = self.combo_status_filter.currentText()

            sql = """
                SELECT 
                    l.log_id, 
                    l.uid, 
                    COALESCE(m.license_plate, 'Unregistered') AS license_plate, 
                    l.time_in, 
                    l.time_out, 
                    l.status, 
                    l.fee_calculated 
                FROM parking_logs l
                LEFT JOIN members m ON l.uid = m.uid
                WHERE 1=1
            """
            params = []

            if search_query:
                sql += " AND (l.uid LIKE ? OR m.license_plate LIKE ?)"
                params.extend([f"%{search_query}%", f"%{search_query}%"])

            if status_filter != "All Status":
                sql += " AND l.status = ?"
                params.append(status_filter)

            sql += " ORDER BY l.log_id DESC"

            self.parking.cursor.execute(sql, params)
            logs_data = self.parking.cursor.fetchall()

            with open(file_path, mode='w', newline='', encoding='utf-8-sig') as file:
                writer = csv.writer(file)
                writer.writerow(["Log ID", "UID", "License Plate", "Time In", "Time Out", "Status", "Fee (THB)"])
                for row in logs_data:
                    writer.writerow(row)

            self.log_message(f"✅ [EXPORT SUCCESS] Parking logs exported to: {file_path}")

        except Exception as e:
            self.log_message(f"❌ Error exporting CSV: {e}")

    def toggle_ntag_read_mode(self):
        self.is_reading_ntag = not self.is_reading_ntag
        if self.is_reading_ntag:
            self.btn_read_ntag.setText("⌛ Waiting for NTAG on ESP32...")
            self.btn_read_ntag.setStyleSheet("background-color: #F9E2AF; color: #11111B;")
            self.log_message("📡 [NTAG READ MODE] Please tap NTAG on ESP32 reader...")
        else:
            self.btn_read_ntag.setText("📡 Tap NTAG to Read UID")
            self.btn_read_ntag.setStyleSheet("background-color: #FAB387; color: #11111B;")
            self.log_message("❌ [NTAG READ MODE] NTAG read mode cancelled")

    def process_scan(self, uid):
        if self.is_reading_ntag:
            self.input_uid.setText(uid)
            self.is_reading_ntag = False
            self.btn_read_ntag.setText("📡 Tap NTAG to Read UID")
            self.btn_read_ntag.setStyleSheet("background-color: #FAB387; color: #11111B;")
            self.tabs.setCurrentIndex(1)
            self.log_message(f"✅ [NTAG CAPTURED] Retrieved UID: {uid} from ESP32 successfully")
            return

        self.log_message(f"\nNFC read: {uid}")
        try:
            query = "SELECT log_id, status FROM parking_logs WHERE uid = ? ORDER BY log_id DESC LIMIT 1"
            self.parking.cursor.execute(query, (uid,))
            row = self.parking.cursor.fetchone()
            
            last_log_id = row[0] if row else None
            current_status = row[1] if row else None

            if current_status == 'paid':
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                update_query = """
                    UPDATE parking_logs 
                    SET status = 'completed', time_out = ? 
                    WHERE log_id = ?
                """
                self.parking.cursor.execute(update_query, (now_str, last_log_id))
                self.parking.conn.commit()

                self.log_message(f"🟢 [GATE OPEN] UID: {uid} - Scanned OUT at {now_str}. STATUS: COMPLETED")
                self.plate_label.setText(f"GATE OPEN - HAVE A SAFE TRIP!\n{uid}")
                self.plate_label.setStyleSheet("background-color: #A6E3A1; color: #11111B; border-radius: 10px; padding: 15px;")
                
                self.send_user_status(uid)

            elif current_status is None or current_status == 'completed':
                # --- PARKING CAPACITY CHECK BEFORE ENTRY ---
                self.parking.cursor.execute("SELECT COUNT(*) FROM parking_logs WHERE status = 'parked'")
                currently_parked = self.parking.cursor.fetchone()[0]

                if currently_parked >= self.total_capacity:
                    self.log_message(f"🔴 [ENTRY DENIED] Parking is FULL ({currently_parked}/{self.total_capacity}). UID: {uid}")
                    self.plate_label.setText(f"PARKING FULL!\nENTRY DENIED")
                    self.plate_label.setStyleSheet("background-color: #F38BA8; color: #11111B; border-radius: 10px; padding: 15px;")
                    self.update_capacity_display()
                    return

                scan_result_message = self.parking.handle_scan(uid)
                self.log_message(f"🚘 [ENTRY SCAN] {scan_result_message}")
                self.update_image(uid)
                self.send_user_status(uid)

            elif current_status == 'parked':
                self.log_message(f"🔴 [GATE CLOSED] UID: {uid} - Payment required before exit!")
                self.plate_label.setText(f"PLEASE PAY FIRST!\n{uid}")
                self.plate_label.setStyleSheet("background-color: #F38BA8; color: #11111B; border-radius: 10px; padding: 15px;")
                self.send_user_status(uid)

            self.handle_read_logs()
            self.update_capacity_display()

        except Exception as e:
            self.log_message(f"Error in process_scan: {e}")

    def log_message(self, text):
        self.log_text.append(text)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def process_exit(self, uid, amount):
        try:
            query = """
                UPDATE parking_logs 
                SET status = 'paid', fee_calculated = ? 
                WHERE uid = ? AND status = 'parked'
            """
            self.parking.cursor.execute(query, (amount, uid))
            self.parking.conn.commit()

            self.log_message(f"💳 [PAYMENT SUCCESS] UID: {uid} Paid THB {amount:.2f} -> STATUS: PAID (Waiting for NFC Exit Scan)")
            self.plate_label.setText(f"PAID: {uid}\nScan NFC at Exit Gate")
            self.plate_label.setStyleSheet("background-color: #F9E2AF; color: #11111B; border-radius: 10px; padding: 15px;")
            
            self.send_user_status(uid)
            self.handle_read_logs()
            self.update_capacity_display()

        except Exception as e:
            self.log_message(f"Error processing payment: {e}")

    def process_search(self, search_query, request_id):
        try:
            query_str = f"%{search_query}%"
            sql = """
                SELECT l.uid, m.license_plate, l.status
                FROM parking_logs l
                LEFT JOIN members m ON l.uid = m.uid
                WHERE (m.license_plate LIKE ? OR l.uid LIKE ?)
                ORDER BY l.log_id DESC LIMIT 1
            """
            self.parking.cursor.execute(sql, (query_str, query_str))
            row = self.parking.cursor.fetchone()

            response_topic = f"parking/search/response/{request_id}"

            if row:
                uid, plate, status = row[0], row[1] if row[1] else "BKK-1234", row[2]
                payload = json.dumps({
                    "found": True,
                    "uid": uid,
                    "plate": plate,
                    "status": status
                })
                self.log_message(f"🔍 [SEARCH MATCH] Query: '{search_query}' -> Found UID: {uid} ({plate})")
            else:
                payload = json.dumps({
                    "found": False,
                    "message": f"Vehicle with plate or UID '{search_query}' not found in the parking system."
                })
                self.log_message(f"🔍 [SEARCH NOT FOUND] Query: '{search_query}'")

            self.pub_client.publish(response_topic, payload)

        except Exception as e:
            self.log_message(f"Error processing search: {e}")

    def send_user_status(self, uid):
        try:
            query = """
                SELECT m.license_plate, l.status, l.time_in, l.image_path 
                FROM parking_logs l 
                LEFT JOIN members m ON l.uid = m.uid 
                WHERE l.uid = ? ORDER BY l.log_id DESC LIMIT 1
            """
            self.parking.cursor.execute(query, (uid,))
            row = self.parking.cursor.fetchone()
            
            plate = 'BKK-1234'
            status = 'parked'
            time_in = None
            img_base64 = None

            if row:
                plate = row[0] if row[0] else 'BKK-1234'
                status = row[1] if row[1] else 'parked'
                time_in = str(row[2]) if row[2] else None
                img_path = row[3] if len(row) > 3 and row[3] else None

                if img_path and os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as img_file:
                            img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                    except Exception as img_err:
                        self.log_message(f"Image base64 read error: {img_err}")

            self.parking.cursor.execute("""
                SELECT time_in, time_out, status, fee_calculated 
                FROM parking_logs 
                WHERE uid = ? 
                ORDER BY log_id DESC 
                LIMIT 5
            """, (uid,))
            history_rows = self.parking.cursor.fetchall()
            
            history_list = []
            for h in history_rows:
                history_list.append({
                    "time_in": str(h[0]) if h[0] else "-",
                    "time_out": str(h[1]) if h[1] else "-",
                    "status": h[2] if h[2] else "-",
                    "fee": h[3] if h[3] is not None else 0.0
                })

            payload = json.dumps({
                "uid": uid,
                "plate": plate,
                "status": status,
                "time_in": time_in,
                "image_base64": img_base64,
                "history": history_list,
                "zone": "Floor 2 - Zone B14"
            })

            self.pub_client.publish(f"parking/status/{uid}", payload)
            self.pub_client.publish("parking/scan/live", payload)

        except Exception as e:
            self.log_message(f"Error sending status: {e}")

    def update_image(self, uid):
        query = "SELECT image_path, status FROM parking_logs WHERE uid = ? ORDER BY log_id DESC LIMIT 1"
        self.parking.cursor.execute(query, (uid,))
        result = self.parking.cursor.fetchone()
        
        if result and result[0]:
            img_path = result[0]
            status = result[1]
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path)
                scaled_pixmap = pixmap.scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio)
                self.image_display.setPixmap(scaled_pixmap)
                
                if status == 'parked':
                    self.plate_label.setText(f"Entry: {result}")
                    self.plate_label.setStyleSheet("background-color: #313244; color: #A6E3A1; border-radius: 10px; padding: 15px;")
                else:
                    self.plate_label.setText(f"Exit: {result}")
                    self.plate_label.setStyleSheet("background-color: #313244; color: #F9E2AF; border-radius: 10px; padding: 15px;")

    def simulate_scan(self, uid):
        self.process_scan(uid)

    def closeEvent(self, event):
        self.mqtt_thread.stop()
        if hasattr(self, 'pub_client'):
            self.pub_client.loop_stop()
            self.pub_client.disconnect()
        event.accept()

    def autofill_form(self, row, column):
        self.input_uid.setText(self.table_members.item(row, 0).text())
        self.input_plate.setText(self.table_members.item(row, 1).text())
        self.input_type.setText(self.table_members.item(row, 2).text())

    def handle_read(self):
        members_data = self.parking.read_all_members()
        self.table_members.setRowCount(len(members_data))
        for row_idx, row_data in enumerate(members_data):
            for col_idx, item_data in enumerate(row_data):
                self.table_members.setItem(row_idx, col_idx, QTableWidgetItem(str(item_data)))

    def handle_create(self):
        uid = self.input_uid.text().strip()
        plate = self.input_plate.text().strip()
        m_type = self.input_type.text().strip()
        if not uid or not plate: return
        success, msg = self.parking.create_member(uid, plate, m_type)
        if success: 
            self.log_message(f"✅ {msg}")
            self.handle_read()
        else:
            self.log_message(f"❌ {msg}")

    def handle_update(self):
        uid = self.input_uid.text().strip()
        plate = self.input_plate.text().strip()
        m_type = self.input_type.text().strip()
        if not uid: return
        success, msg = self.parking.update_member(uid, plate, m_type)
        if success: self.handle_read()

    def handle_delete(self):
        uid = self.input_uid.text().strip()
        if not uid: return
        success, msg = self.parking.delete_member(uid)
        if success: self.handle_read()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParkingDashboard()
    window.show()
    sys.exit(app.exec())