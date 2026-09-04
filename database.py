import sqlite3
import csv
import os
import threading
from datetime import datetime

DB_FILE = os.path.join(os.path.dirname(__file__), "bot_data.db")
CSV_FILE = os.path.join(os.path.dirname(__file__), "saved_numbers_sheet.csv")

db_lock = threading.Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS saved_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                phone TEXT NOT NULL,
                order_id TEXT,
                name TEXT,
                age TEXT,
                location TEXT,
                relatives TEXT,
                google_status TEXT
            )
        ''')
        conn.commit()
        conn.close()

        # Initialize CSV file with headers if it does not exist
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Timestamp", "Phone", "Order ID", "Name", "Age", "Location", "Relatives", "Google Status"
                ])

def save_record(phone, order_id="", name="", age="", location="", relatives="", google_status="Verified"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with db_lock:
        # Save to SQLite
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO saved_records (timestamp, phone, order_id, name, age, location, relatives, google_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, phone, order_id, name, age, location, relatives, google_status))
        record_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Append to CSV
        with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, phone, order_id, name, age, location, relatives, google_status])

    return {
        "id": record_id,
        "timestamp": timestamp,
        "phone": phone,
        "order_id": order_id,
        "name": name,
        "age": age,
        "location": location,
        "relatives": relatives,
        "google_status": google_status
    }

def get_all_records():
    with db_lock:
        if not os.path.exists(DB_FILE):
            return []
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM saved_records ORDER BY id DESC')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

def get_record_count():
    with db_lock:
        if not os.path.exists(DB_FILE):
            return 0
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM saved_records')
        count = cursor.fetchone()[0]
        conn.close()
        return count
