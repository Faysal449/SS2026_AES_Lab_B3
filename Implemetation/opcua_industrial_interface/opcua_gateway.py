import json
import socket
import threading
import time
from datetime import datetime

from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
from opcua import Server


# =========================
# Network settings
# =========================
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 5000

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_FLAME = "factory/flame"

UDP_HOST = "0.0.0.0"
UDP_PORT = 6000

OPCUA_ENDPOINT = "opc.tcp://0.0.0.0:4840/factory/server/"


# =========================
# Shared sensor data
# =========================
lock = threading.Lock()

data = {
    "temperature": {
        "online": False,
        "temperature_c": 0.0,
        "humidity_percent": 0.0,
        "status": "NO_DATA",
        "last_update": "never",
        "last_seen": 0
    },

    "flame": {
        "online": False,
        "flame_raw": 0,
        "flame_detected": False,
        "status": "NO_DATA",
        "last_update": "never",
        "last_seen": 0
    },

    "vibration": {
        "online": False,
        "accelerometer_available": False,
        "samples": 0,
        "ax": 0.0,
        "ay": 0.0,
        "az": 0.0,
        "accel_magnitude": 0.0,
        "baseline_magnitude": 0.0,
        "vibration_rms": 0.0,
        "vibration_g": 0.0,
        "vibration_peak": 0.0,
        "magnitude_peak_to_peak": 0.0,
        "vibration_status": "NO_DATA",
        "last_update": "never",
        "last_seen": 0
    },

    "gateway": {
        "overall_status": "NO_DATA",
        "overall_alarm": False,
        "last_update": "never"
    }
}


# =========================
# Helper functions
# =========================
def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def update_temperature_status():
    temp = data["temperature"]

    if not temp["online"]:
        temp["status"] = "NO_DATA"
        return

    temperature = temp["temperature_c"]
    humidity = temp["humidity_percent"]

    if temperature >= 45:
        temp["status"] = "CRITICAL"
    elif temperature >= 35 or humidity >= 80:
        temp["status"] = "WARNING"
    else:
        temp["status"] = "NORMAL"


def update_flame_status():
    flame = data["flame"]

    if not flame["online"]:
        flame["status"] = "NO_DATA"
        return

    if flame["flame_detected"]:
        flame["status"] = "ALARM"
    else:
        flame["status"] = "NORMAL"


def update_gateway_status():
    temp_status = data["temperature"]["status"]
    flame_status = data["flame"]["status"]
    vibration_status = data["vibration"]["vibration_status"]

    critical_conditions = [
        temp_status == "CRITICAL",
        flame_status == "ALARM",
        vibration_status == "CRITICAL"
    ]

    warning_conditions = [
        temp_status == "WARNING",
        vibration_status == "WARNING",
        temp_status == "NO_DATA",
        flame_status == "NO_DATA",
        vibration_status == "NO_DATA"
    ]

    if any(critical_conditions):
        data["gateway"]["overall_status"] = "CRITICAL"
        data["gateway"]["overall_alarm"] = True
    elif any(warning_conditions):
        data["gateway"]["overall_status"] = "WARNING"
        data["gateway"]["overall_alarm"] = False
    else:
        data["gateway"]["overall_status"] = "NORMAL"
        data["gateway"]["overall_alarm"] = False

    data["gateway"]["last_update"] = now_string()


def check_sensor_online_status():
    current_time = time.time()

    # If no data for 10 seconds, mark sensor offline
    timeout = 10

    if current_time - data["temperature"]["last_seen"] > timeout:
        data["temperature"]["online"] = False

    if current_time - data["flame"]["last_seen"] > timeout:
        data["flame"]["online"] = False

    if current_time - data["vibration"]["last_seen"] > timeout:
        data["vibration"]["online"] = False
        data["vibration"]["vibration_status"] = "NO_DATA"

    update_temperature_status()
    update_flame_status()
    update_gateway_status()


# =========================
# HTTP server for DHT11
# =========================
app = Flask(__name__)


@app.route("/temperature", methods=["POST"])
def receive_temperature():
    try:
        payload = request.get_json(force=True)

        with lock:
            data["temperature"]["temperature_c"] = safe_float(payload.get("temperature_c"))
            data["temperature"]["humidity_percent"] = safe_float(payload.get("humidity_percent"))
            data["temperature"]["online"] = True
            data["temperature"]["last_update"] = now_string()
            data["temperature"]["last_seen"] = time.time()

            update_temperature_status()
            update_gateway_status()

        print("[HTTP] Temperature received:", payload)
        return jsonify({"status": "ok", "message": "temperature received"}), 200

    except Exception as e:
        print("[HTTP] Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 400


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "Raspberry Pi Smart Factory Gateway running",
        "http_temperature_endpoint": "/temperature",
        "mqtt_topic": MQTT_TOPIC_FLAME,
        "udp_port": UDP_PORT,
        "opcua_endpoint": OPCUA_ENDPOINT
    })


def start_http_server():
    print(f"[HTTP] Server running on port {HTTP_PORT}")
    app.run(host=HTTP_HOST, port=HTTP_PORT, debug=False, use_reloader=False)


# =========================
# MQTT subscriber for Flame sensor
# =========================
def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Connected to broker")
        client.subscribe(MQTT_TOPIC_FLAME)
        print("[MQTT] Subscribed to:", MQTT_TOPIC_FLAME)
    else:
        print("[MQTT] Connection failed, rc =", rc)


def on_mqtt_message(client, userdata, msg):
    try:
        payload_text = msg.payload.decode("utf-8")
        payload = json.loads(payload_text)

        with lock:
            data["flame"]["flame_raw"] = safe_int(payload.get("flame_raw"))
            data["flame"]["flame_detected"] = bool(payload.get("flame_detected"))
            data["flame"]["online"] = True
            data["flame"]["last_update"] = now_string()
            data["flame"]["last_seen"] = time.time()

            update_flame_status()
            update_gateway_status()

        print("[MQTT] Flame received:", payload)

    except Exception as e:
        print("[MQTT] Error:", e)


def start_mqtt_client():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id="raspberry_pi_gateway")
    except Exception:
        client = mqtt.Client(client_id="raspberry_pi_gateway")

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    while True:
        try:
            print("[MQTT] Connecting to broker...")
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as e:
            print("[MQTT] Broker connection error:", e)
            time.sleep(5)


# =========================
# UDP receiver for IMU / vibration sensor
# =========================
def start_udp_server():
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.bind((UDP_HOST, UDP_PORT))

    print(f"[UDP] Listening on port {UDP_PORT}")

    while True:
        try:
            message, address = udp_socket.recvfrom(4096)
            payload_text = message.decode("utf-8").strip()
            payload = json.loads(payload_text)

            with lock:
                data["vibration"]["accelerometer_available"] = bool(payload.get("accelerometer_available", False))
                data["vibration"]["samples"] = safe_int(payload.get("samples"))
                data["vibration"]["ax"] = safe_float(payload.get("ax"))
                data["vibration"]["ay"] = safe_float(payload.get("ay"))
                data["vibration"]["az"] = safe_float(payload.get("az"))
                data["vibration"]["accel_magnitude"] = safe_float(payload.get("accel_magnitude"))
                data["vibration"]["baseline_magnitude"] = safe_float(payload.get("baseline_magnitude"))
                data["vibration"]["vibration_rms"] = safe_float(payload.get("vibration_rms"))
                data["vibration"]["vibration_g"] = safe_float(payload.get("vibration_g"))
                data["vibration"]["vibration_peak"] = safe_float(payload.get("vibration_peak"))
                data["vibration"]["magnitude_peak_to_peak"] = safe_float(payload.get("magnitude_peak_to_peak"))
                data["vibration"]["vibration_status"] = str(payload.get("vibration_status", "NO_DATA"))

                data["vibration"]["online"] = True
                data["vibration"]["last_update"] = now_string()
                data["vibration"]["last_seen"] = time.time()

                update_gateway_status()

            print("[UDP] Vibration received from", address, ":", payload)

        except Exception as e:
            print("[UDP] Error:", e)


# =========================
# OPC UA server
# =========================
def start_opcua_server():
    server = Server()
    server.set_endpoint(OPCUA_ENDPOINT)
    server.set_server_name("Smart Factory Raspberry Pi OPC UA Server")

    namespace_uri = "http://smartfactory.local"
    idx = server.register_namespace(namespace_uri)

    objects = server.get_objects_node()
    factory = objects.add_object(idx, "SmartFactory")

    # Temperature node
    temp_node = factory.add_object(idx, "TemperatureNode")
    opc_temp_online = temp_node.add_variable(idx, "Online", False)
    opc_temperature = temp_node.add_variable(idx, "Temperature_C", 0.0)
    opc_humidity = temp_node.add_variable(idx, "Humidity_Percent", 0.0)
    opc_temp_status = temp_node.add_variable(idx, "Temperature_Status", "NO_DATA")
    opc_temp_last_update = temp_node.add_variable(idx, "Last_Update", "never")

    # Flame node
    flame_node = factory.add_object(idx, "FlameNode")
    opc_flame_online = flame_node.add_variable(idx, "Online", False)
    opc_flame_raw = flame_node.add_variable(idx, "Flame_Raw", 0)
    opc_flame_detected = flame_node.add_variable(idx, "Flame_Detected", False)
    opc_flame_status = flame_node.add_variable(idx, "Flame_Status", "NO_DATA")
    opc_flame_last_update = flame_node.add_variable(idx, "Last_Update", "never")

    # Vibration node
    vibration_node = factory.add_object(idx, "VibrationNode")
    opc_vib_online = vibration_node.add_variable(idx, "Online", False)
    opc_acc_available = vibration_node.add_variable(idx, "Accelerometer_Available", False)
    opc_samples = vibration_node.add_variable(idx, "Samples", 0)
    opc_ax = vibration_node.add_variable(idx, "AX_ms2", 0.0)
    opc_ay = vibration_node.add_variable(idx, "AY_ms2", 0.0)
    opc_az = vibration_node.add_variable(idx, "AZ_ms2", 0.0)
    opc_accel_mag = vibration_node.add_variable(idx, "Acceleration_Magnitude_ms2", 0.0)
    opc_vib_rms = vibration_node.add_variable(idx, "Vibration_RMS_ms2", 0.0)
    opc_vib_g = vibration_node.add_variable(idx, "Vibration_G", 0.0)
    opc_vib_peak = vibration_node.add_variable(idx, "Vibration_Peak_ms2", 0.0)
    opc_vib_p2p = vibration_node.add_variable(idx, "Magnitude_Peak_To_Peak_ms2", 0.0)
    opc_vib_status = vibration_node.add_variable(idx, "Vibration_Status", "NO_DATA")
    opc_vib_last_update = vibration_node.add_variable(idx, "Last_Update", "never")

    # Gateway / industrial processed data
    gateway_node = factory.add_object(idx, "GatewayProcessedData")
    opc_overall_status = gateway_node.add_variable(idx, "Overall_Status", "NO_DATA")
    opc_overall_alarm = gateway_node.add_variable(idx, "Overall_Alarm", False)
    opc_gateway_last_update = gateway_node.add_variable(idx, "Last_Update", "never")

    server.start()
    print("[OPC UA] Server started")
    print("[OPC UA] Endpoint:", OPCUA_ENDPOINT)

    try:
        while True:
            with lock:
                check_sensor_online_status()

                # Temperature OPC UA update
                opc_temp_online.set_value(data["temperature"]["online"])
                opc_temperature.set_value(data["temperature"]["temperature_c"])
                opc_humidity.set_value(data["temperature"]["humidity_percent"])
                opc_temp_status.set_value(data["temperature"]["status"])
                opc_temp_last_update.set_value(data["temperature"]["last_update"])

                # Flame OPC UA update
                opc_flame_online.set_value(data["flame"]["online"])
                opc_flame_raw.set_value(data["flame"]["flame_raw"])
                opc_flame_detected.set_value(data["flame"]["flame_detected"])
                opc_flame_status.set_value(data["flame"]["status"])
                opc_flame_last_update.set_value(data["flame"]["last_update"])

                # Vibration OPC UA update
                opc_vib_online.set_value(data["vibration"]["online"])
                opc_acc_available.set_value(data["vibration"]["accelerometer_available"])
                opc_samples.set_value(data["vibration"]["samples"])
                opc_ax.set_value(data["vibration"]["ax"])
                opc_ay.set_value(data["vibration"]["ay"])
                opc_az.set_value(data["vibration"]["az"])
                opc_accel_mag.set_value(data["vibration"]["accel_magnitude"])
                opc_vib_rms.set_value(data["vibration"]["vibration_rms"])
                opc_vib_g.set_value(data["vibration"]["vibration_g"])
                opc_vib_peak.set_value(data["vibration"]["vibration_peak"])
                opc_vib_p2p.set_value(data["vibration"]["magnitude_peak_to_peak"])
                opc_vib_status.set_value(data["vibration"]["vibration_status"])
                opc_vib_last_update.set_value(data["vibration"]["last_update"])

                # Processed gateway status
                opc_overall_status.set_value(data["gateway"]["overall_status"])
                opc_overall_alarm.set_value(data["gateway"]["overall_alarm"])
                opc_gateway_last_update.set_value(data["gateway"]["last_update"])

            time.sleep(1)

    finally:
        server.stop()
        print("[OPC UA] Server stopped")


# =========================
# Main
# =========================
if __name__ == "__main__":
    print("==============================================")
    print(" Raspberry Pi Smart Factory OPC UA Gateway")
    print("==============================================")
    print("HTTP temperature receiver :", f"http://<pi-ip>:{HTTP_PORT}/temperature")
    print("MQTT flame topic          :", MQTT_TOPIC_FLAME)
    print("UDP vibration port        :", UDP_PORT)
    print("OPC UA endpoint           :", OPCUA_ENDPOINT)
    print("==============================================")

    http_thread = threading.Thread(target=start_http_server, daemon=True)
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    udp_thread = threading.Thread(target=start_udp_server, daemon=True)

    http_thread.start()
    mqtt_thread.start()
    udp_thread.start()

    start_opcua_server()
