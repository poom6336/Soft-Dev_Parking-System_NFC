import sys
import os
import time
import serial
import paho.mqtt.client as mqtt
from adafruit_pn532.uart import PN532_UART
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QFormLayout, QLineEdit, QTableWidget, QHeaderView,
                             QTableWidgetItem, QMessageBox, QTabWidget)
from PyQt6.QtGui import QPixmap, QFont
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from parkSysDemo import ParkingSys

class MQTTListenerThread(QThread):
    card_scanned = pyqtSignal(str)
    log_msg = pyqtSignal(str)

    def __init__(self, broker_address="test.mosquitto.org", topic="parking/entry/scan"):
        super().__init__()
        self.broker = broker_address
        self.topic = topic
        self.client = mqtt.Client()
        self.is_running = True

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.log_msg.emit(f"Connect to MQTT Broker: {self.broker} success")
            self.client.subscribe(self.topic)
        else:
            self.log_msg.emit(f"Fail to connect to MQTT (code: {rc})")

    def on_message(self, client, userdata, msg):
        uid_hex = msg.payload.decode("utf-8")
        self.card_scanned.emit(uid_hex)

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

        #demo db
        self.parking.register_member('A1B2C3D4', 'กท-2058')
        self.parking.register_member('E5F6G7H8', 'สข-9999', 'vip')

        self.setWindowTitle("SMART PARKING TERMINAL")
        self.resize(1000, 600)

        self.setStyleSheet("""
            QMainWindow, QWidget#tab_bg {
                background-color: #1E1E2E;
            }
            QLabel { color: #CDD6F4; }
            QTextEdit, QLineEdit, QTableWidget {
                background-color: #181825;
                color: #A6E3A1;
                border: 1px solid #45475A;
                border-radius: 8px;
                padding: 5px;
            }
            QTableWidget {
                color: #CDD6F4;
            }
            QHeaderView::section {
                background-color: #313244;
                color: #CDD6F4;
                border: none;
                padding: 4px;
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
        
        self.tabs.addTab(self.tab_dashboard, "🎥 Live Dashboard")
        self.tabs.addTab(self.tab_management, "⚙️ Database Management")

        self.setup_dashboard_tab()
        self.setup_management_tab()
    
        self.handle_read()

        # NFC Thread
        self.log_message("SYSTEM INITIALIZED. READY.")
        self.mqtt_thread = MQTTListenerThread(broker_address="test.mosquitto.org", topic="parking/entry/scan")
        self.mqtt_thread.card_scanned.connect(self.process_scan)
        self.mqtt_thread.log_msg.connect(self.log_message)
        self.mqtt_thread.start()

    def setup_dashboard_tab(self):
        main_layout = QHBoxLayout()

        # left part
        left_layout = QVBoxLayout()

        self.plate_label = QLabel("Waiting for user")
        self.plate_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
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
        self.image_display.setFixedSize(450, 320)

        left_layout.addWidget(self.plate_label)
        left_layout.addWidget(self.image_display)
        left_layout.addStretch()

        main_layout.addLayout(left_layout)

        # right part
        right_layout = QVBoxLayout()

        title_log = QLabel("LIVE SYSTEM LOGS")
        title_log.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_log.setStyleSheet("color: #FAB387;")

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))

        btn_layout = QHBoxLayout()
        btn_scan_car1 = QPushButton("Scan: กท-2058")
        btn_scan_car1.setStyleSheet("background-color: #CBA6F7;")
        btn_scan_car1.clicked.connect(lambda: self.simulate_scan('A1B2C3D4'))

        btn_scan_car2 = QPushButton("Scan: สข-9999")
        btn_scan_car2.setStyleSheet("background-color: #CBA6F7;")
        btn_scan_car2.clicked.connect(lambda: self.simulate_scan('E5F6G7H8'))
        
        btn_layout.addWidget(btn_scan_car1)
        btn_layout.addWidget(btn_scan_car2)

        right_layout.addWidget(title_log)
        right_layout.addWidget(self.log_text)
        right_layout.addLayout(btn_layout)

        main_layout.addLayout(right_layout)
        
        self.tab_dashboard.setLayout(main_layout)

    def log_message(self, text):
        self.log_text.append(text)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def process_scan(self, uid):
        self.log_message(f"\nNFC read: {uid}")
        try:
            scan_result_message = self.parking.handle_scan(uid)
            self.log_message(scan_result_message)
            self.update_image(uid)

        except Exception as e:
            self.log_message(f"Error: {e}")

    def update_image(self, uid):
        self.parking.cursor.execute('''
            SELECT image_path, status FROM parking_logs 
            WHERE uid = ? ORDER BY time_in DESC LIMIT 1
        ''', (uid,))
        
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
            else:
                self.log_message(f"Image not found: {img_path}")

    def simulate_scan(self, uid):
        self.log_message(f"\nScanning UID: {uid}")
        
        try:
            scan_result = self.parking.handle_scan(uid)
            self.log_message(scan_result)
            self.update_image(uid)
            
        except Exception as e:
            self.log_message(f"Error: {e}")

    def closeEvent(self, event):
        self.log_message("Exitting")
        self.mqtt_thread.stop()
        event.accept()

    # Tab 2 (Management)
    def setup_management_tab(self):
        layout = QHBoxLayout()
        
        # L panel: Form, buttons
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("Database management", font=QFont("Segoe UI", 12, QFont.Weight.Bold)))
        
        # Create form
        form_layout = QFormLayout()
        self.input_uid = QLineEdit()
        self.input_uid.setPlaceholderText("Fill UID")
        
        self.input_plate = QLineEdit()
        self.input_plate.setPlaceholderText("Fill license plate")
        
        self.input_type = QLineEdit()
        self.input_type.setText("regular")
        
        form_layout.addRow("UID:", self.input_uid)
        form_layout.addRow("License plate:", self.input_plate)
        form_layout.addRow("Type:", self.input_type)
        left_panel.addLayout(form_layout)
        
        # CRUD buttons
        btn_create = QPushButton("Add new member")
        btn_create.clicked.connect(self.handle_create)
        
        btn_update = QPushButton("Update data (Search with UID)")
        btn_update.setStyleSheet("background-color: #F9E2AF; color: #11111B;")
        btn_update.clicked.connect(self.handle_update)
        
        btn_delete = QPushButton("Delete member search with UID")
        btn_delete.setStyleSheet("background-color: #F38BA8; color: #11111B;")
        btn_delete.clicked.connect(self.handle_delete)
        
        btn_read = QPushButton("Refresh table")
        btn_read.clicked.connect(self.handle_read)

        left_panel.addWidget(btn_create)
        left_panel.addWidget(btn_update)
        left_panel.addWidget(btn_delete)
        left_panel.addSpacing(20)
        left_panel.addWidget(btn_read)
        left_panel.addStretch() 
        
        layout.addLayout(left_panel, stretch=1)

        # R panel: display
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

    # Connect button function with database
    # Data from table to input
    def autofill_form(self, row, column):
        uid = self.table_members.item(row, 0).text()
        plate = self.table_members.item(row, 1).text()
        m_type = self.table_members.item(row, 2).text()
        
        self.input_uid.setText(uid)
        self.input_plate.setText(plate)
        self.input_type.setText(m_type)

    # Read data and display to table
    def handle_read(self):
        members_data = self.parking.read_all_members()
        
        self.table_members.setRowCount(len(members_data))
        
        for row_idx, row_data in enumerate(members_data):
            for col_idx, item_data in enumerate(row_data):
                self.table_members.setItem(row_idx, col_idx, QTableWidgetItem(str(item_data)))

    # Create new member
    def handle_create(self):
        uid = self.input_uid.text().strip()
        plate = self.input_plate.text().strip()
        m_type = self.input_type.text().strip()
        
        if not uid or not plate:
            QMessageBox.warning(self, "[Warning]", "Please assign UID and license plate.")
            return
            
        success, msg = self.parking.create_member(uid, plate, m_type)
        if success:
            QMessageBox.information(self, "[Success]", msg)
            self.handle_read()
            self.input_uid.clear()
            self.input_plate.clear()
        else:
            QMessageBox.critical(self, "[Error]", msg)

    def handle_update(self):
        uid = self.input_uid.text().strip()
        plate = self.input_plate.text().strip()
        m_type = self.input_type.text().strip()
        
        if not uid:
            QMessageBox.warning(self, "[Warning]", "Please assign UID")
            return
            
        success, msg = self.parking.update_member(uid, plate, m_type)
        if success:
            QMessageBox.information(self, "[Success]", msg)
            self.handle_read()
        else:
            QMessageBox.critical(self, "[Error]", msg)

    def handle_delete(self):
        """ [D] ลบสมาชิก """
        uid = self.input_uid.text().strip()
        
        if not uid:
            QMessageBox.warning(self, "[Warning]", "Please assign UID")
            return

        # confirm before delete
        confirm = QMessageBox.question(
            self, "[Delete confirmation]", f"Are you sure you want to delete UID {uid} ?\n(All of this UID parking logs will also be deleted)", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            success, msg = self.parking.delete_member(uid)
            if success:
                QMessageBox.information(self, "[Success]", msg)
                self.handle_read()
                self.input_uid.clear()
            else:
                QMessageBox.critical(self, "[Error]", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ParkingDashboard()
    window.show()
    sys.exit(app.exec())