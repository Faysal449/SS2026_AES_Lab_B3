"""
02_historian_sqlite.py
Historian layer.

Purpose:
- Reads OPC UA data once per second.
- Stores live synthetic data into SQLite database and CSV report.
- This becomes the data source for MES and ERP.

Run after 00 and 01:
    python3 02_historian_sqlite.py
"""

import csv
import os
import sqlite3
import time
from datetime import datetime
from opcua import Client

OPCUA_URL = "opc.tcp://127.0.0.1:4840/factory/server/"
NAMESPACE_URI = "http://smartfactory.local"
DB_FILE = "factory_history.db"
CSV_FILE = "live_factory_data.csv"


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_child(parent, idx, name):
    return parent.get_child([f"{idx}:{name}"])


def setup_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS factory_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            temperature_c REAL,
            humidity_percent REAL,
            temperature_status TEXT,
            flame_raw INTEGER,
            flame_detected INTEGER,
            flame_status TEXT,
            vibration_rms REAL,
            vibration_g REAL,
            vibration_status TEXT,
            overall_status TEXT,
            overall_alarm INTEGER,
            machine_state TEXT,
            motor_command INTEGER,
            fan_command INTEGER,
            buzzer_command INTEGER,
            emergency_stop INTEGER
        )
        """
    )
    conn.commit()
    return conn


def setup_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "temperature_c", "humidity_percent", "temperature_status",
                "flame_raw", "flame_detected", "flame_status",
                "vibration_rms", "vibration_g", "vibration_status",
                "overall_status", "overall_alarm", "machine_state", "motor_command",
                "fan_command", "buzzer_command", "emergency_stop"
            ])


def main():
    conn = setup_db()
    setup_csv()
    cur = conn.cursor()

    while True:
        client = Client(OPCUA_URL)
        try:
            print("[02 HISTORIAN] Connecting to OPC UA server...")
            client.connect()
            print("[02 HISTORIAN] Connected")

            idx = client.get_namespace_index(NAMESPACE_URI)
            smart_factory = get_child(client.nodes.objects, idx, "SmartFactory")
            temp_node = get_child(smart_factory, idx, "TemperatureNode")
            flame_node = get_child(smart_factory, idx, "FlameNode")
            vib_node = get_child(smart_factory, idx, "VibrationNode")
            gateway_node = get_child(smart_factory, idx, "GatewayProcessedData")
            plc_node = get_child(smart_factory, idx, "PLCControl")

            nodes = {
                "temperature_c": get_child(temp_node, idx, "Temperature_C"),
                "humidity_percent": get_child(temp_node, idx, "Humidity_Percent"),
                "temperature_status": get_child(temp_node, idx, "Temperature_Status"),
                "flame_raw": get_child(flame_node, idx, "Flame_Raw"),
                "flame_detected": get_child(flame_node, idx, "Flame_Detected"),
                "flame_status": get_child(flame_node, idx, "Flame_Status"),
                "vibration_rms": get_child(vib_node, idx, "Vibration_RMS_ms2"),
                "vibration_g": get_child(vib_node, idx, "Vibration_G"),
                "vibration_status": get_child(vib_node, idx, "Vibration_Status"),
                "overall_status": get_child(gateway_node, idx, "Overall_Status"),
                "overall_alarm": get_child(gateway_node, idx, "Overall_Alarm"),
                "machine_state": get_child(plc_node, idx, "Machine_State"),
                "motor_command": get_child(plc_node, idx, "Motor_Command"),
                "fan_command": get_child(plc_node, idx, "Fan_Command"),
                "buzzer_command": get_child(plc_node, idx, "Buzzer_Command"),
                "emergency_stop": get_child(plc_node, idx, "Emergency_Stop"),
            }

            while True:
                row = {key: node.get_value() for key, node in nodes.items()}
                row["timestamp"] = now_string()

                values = [
                    row["timestamp"], row["temperature_c"], row["humidity_percent"], row["temperature_status"],
                    row["flame_raw"], int(row["flame_detected"]), row["flame_status"],
                    row["vibration_rms"], row["vibration_g"], row["vibration_status"],
                    row["overall_status"], int(row["overall_alarm"]), row["machine_state"], int(row["motor_command"]),
                    int(row["fan_command"]), int(row["buzzer_command"]), int(row["emergency_stop"]),
                ]

                cur.execute(
                    """
                    INSERT INTO factory_history (
                        timestamp, temperature_c, humidity_percent, temperature_status,
                        flame_raw, flame_detected, flame_status,
                        vibration_rms, vibration_g, vibration_status,
                        overall_status, overall_alarm, machine_state, motor_command,
                        fan_command, buzzer_command, emergency_stop
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                conn.commit()

                with open(CSV_FILE, "a", newline="") as f:
                    csv.writer(f).writerow(values)

                print(f"[02 HISTORIAN] Saved row at {row['timestamp']} | State={row['machine_state']} | Overall={row['overall_status']}")
                time.sleep(1)

        except Exception as e:
            print("[02 HISTORIAN] Error:", e)
            try:
                client.disconnect()
            except Exception:
                pass
            print("[02 HISTORIAN] Reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
