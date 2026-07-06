"""
===========================================================
 Smart Factory Raspberry Pi Gateway
===========================================================

Project idea:
-------------
This Raspberry Pi acts as the central industrial gateway.

It receives sensor data from three different Arduino sensor nodes:

1. Temperature / Humidity Node
   - Protocol : HTTP
   - Endpoint : POST /temperature
   - Port     : 5000

2. Flame Sensor Node
   - Protocol : MQTT
   - Broker   : Mosquitto on Raspberry Pi
   - Topic    : factory/flame
   - Port     : 1883

3. Vibration / MPU6050 Node
   - Protocol : UDP
   - Port     : 6000

After receiving the data, this gateway:
- stores the latest sensor values,
- checks status conditions,
- generates NORMAL / WARNING / CRITICAL / ALARM states,
- exposes all processed data using OPC UA.

The dashboard can then read the OPC UA server and visualize the live data.

===========================================================
"""

# =========================================================
# Imports
# =========================================================

import json
import socket
import threading
import time
from datetime import datetime

from flask import Flask, request, jsonify
import paho.mqtt.client as mqtt
from opcua import Server


# =========================================================
# Network Configuration
# =========================================================

# HTTP server configuration
# 0.0.0.0 means the Raspberry Pi listens on all network interfaces.
HTTP_HOST = "0.0.0.0"
HTTP_PORT = 5000

# MQTT configuration
# Mosquitto broker is expected to run locally on the Raspberry Pi.
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_FLAME = "factory/flame"

# UDP configuration for vibration / IMU data
UDP_HOST = "0.0.0.0"
UDP_PORT = 6000

# OPC UA server endpoint
# The dashboard or any OPC UA client connects to this endpoint.
OPCUA_ENDPOINT = "opc.tcp://0.0.0.0:4840/factory/server/"
OPCUA_NAMESPACE_URI = "http://smartfactory.local"

# If a sensor sends no data for this time, it is marked offline.
SENSOR_TIMEOUT_SECONDS = 10


# =========================================================
# Flask App
# =========================================================

# Flask is used for the HTTP receiver.
app = Flask(__name__)


# =========================================================
# Shared Gateway Data
# =========================================================

"""
The gateway receives data from HTTP, MQTT, UDP, and at the same time
the OPC UA server reads this data.

Because multiple threads access the same data, a lock is used.

lock = threading.Lock()
Meaning:
- Only one thread can update/read the shared data at a time.
- This prevents race conditions and corrupted values.
"""

lock = threading.Lock()


"""
This dictionary is the central memory of the gateway.

All incoming sensor values are stored here first.
Then the OPC UA server reads from this dictionary and publishes the values.
"""

data = {
    "temperature": {
        "online": False,
        "temperature_c": 0.0,
        "humidity_percent": 0.0,
        "status": "NO_DATA",
        "last_update": "never",
        "last_seen": 0.0,
    },

    "flame": {
        "online": False,
        "flame_raw": 0,
        "flame_detected": False,
        "status": "NO_DATA",
        "last_update": "never",
        "last_seen": 0.0,
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
        "last_seen": 0.0,
    },

    "gateway": {
        "overall_status": "NO_DATA",
        "overall_alarm": False,
        "last_update": "never",
    },
}


# =========================================================
# Helper Functions
# =========================================================

def now_string():
    """
    Returns current date and time as a readable string.

    Example:
    2026-07-06 20:30:15
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_float(value, default=0.0):
    """
    Safely convert a value to float.

    Why needed?
    Sensor data may be missing or corrupted.
    This function prevents the gateway from crashing.
    """
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0):
    """
    Safely convert a value to integer.
    """
    try:
        return int(value)
    except Exception:
        return default


def safe_bool(value, default=False):
    """
    Safely convert a value to boolean.

    This supports:
    - real boolean values: true / false
    - string values: "true" / "false"
    - numeric values: 1 / 0
    """
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        value = value.strip().lower()
        if value in ["true", "1", "yes", "on"]:
            return True
        if value in ["false", "0", "no", "off"]:
            return False

    if isinstance(value, (int, float)):
        return value != 0

    return default


# =========================================================
# Status Processing Functions
# =========================================================

def update_temperature_status():
    """
    Decide the temperature node status.

    Rules:
    - NO_DATA   : sensor is offline
    - CRITICAL  : temperature >= 45°C
    - WARNING   : temperature >= 35°C or humidity >= 80%
    - NORMAL    : otherwise
    """

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
    """
    Decide the flame node status.

    Rules:
    - NO_DATA : sensor is offline
    - ALARM   : flame detected
    - NORMAL  : no flame detected
    """

    flame = data["flame"]

    if not flame["online"]:
        flame["status"] = "NO_DATA"
        return

    if flame["flame_detected"]:
        flame["status"] = "ALARM"
    else:
        flame["status"] = "NORMAL"


def update_gateway_status():
    """
    Combine all sensor statuses into one final gateway status.

    This is the edge-processing part.

    Priority:
    1. If any critical/alarm condition exists -> CRITICAL
    2. If any warning or missing data exists  -> WARNING
    3. Otherwise                             -> NORMAL
    """

    temp_status = data["temperature"]["status"]
    flame_status = data["flame"]["status"]
    vibration_status = data["vibration"]["vibration_status"]

    critical_conditions = [
        temp_status == "CRITICAL",
        flame_status == "ALARM",
        vibration_status == "CRITICAL",
    ]

    warning_conditions = [
        temp_status == "WARNING",
        vibration_status == "WARNING",
        temp_status == "NO_DATA",
        flame_status == "NO_DATA",
        vibration_status == "NO_DATA",
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
    """
    Check whether sensors are still online.

    If a sensor has not sent data for SENSOR_TIMEOUT_SECONDS,
    it is marked offline.

    This is important because in an industrial system:
    - wrong data is a problem,
    - but no data is also a problem.
    """

    current_time = time.time()

    # Temperature node timeout check
    if current_time - data["temperature"]["last_seen"] > SENSOR_TIMEOUT_SECONDS:
        data["temperature"]["online"] = False

    # Flame node timeout check
    if current_time - data["flame"]["last_seen"] > SENSOR_TIMEOUT_SECONDS:
        data["flame"]["online"] = False

    # Vibration node timeout check
    if current_time - data["vibration"]["last_seen"] > SENSOR_TIMEOUT_SECONDS:
        data["vibration"]["online"] = False
        data["vibration"]["vibration_status"] = "NO_DATA"

    # Recalculate all statuses after checking online/offline state
    update_temperature_status()
    update_flame_status()
    update_gateway_status()


# =========================================================
# HTTP Receiver for DHT11 Temperature Node
# =========================================================

@app.route("/temperature", methods=["POST"])
def receive_temperature():
    """
    HTTP receiver endpoint for the DHT11 temperature node.

    Arduino sends HTTP POST request to:
    http://<raspberry-pi-ip>:5000/temperature

    Example JSON payload:
    {
        "device": "dht11_node",
        "sample": 1,
        "temperature_c": 26.5,
        "humidity_percent": 60.0
    }

    Important line:
    @app.route("/temperature", methods=["POST"])
    This line creates the HTTP receiver endpoint.
    """

    try:
        # Read JSON body from HTTP request
        payload = request.get_json(force=True)

        with lock:
            # Store latest temperature values
            data["temperature"]["temperature_c"] = safe_float(payload.get("temperature_c"))
            data["temperature"]["humidity_percent"] = safe_float(payload.get("humidity_percent"))

            # Mark sensor online and update timestamps
            data["temperature"]["online"] = True
            data["temperature"]["last_update"] = now_string()
            data["temperature"]["last_seen"] = time.time()

            # Update individual and overall status
            update_temperature_status()
            update_gateway_status()

        print("[HTTP] Temperature received:", payload)

        return jsonify({
            "status": "ok",
            "message": "temperature received"
        }), 200

    except Exception as e:
        print("[HTTP] Error:", e)

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400


@app.route("/", methods=["GET"])
def home():
    """
    Simple status page for checking whether the gateway is running.

    Open this in browser:
    http://<raspberry-pi-ip>:5000/
    """

    return jsonify({
        "message": "Raspberry Pi Smart Factory Gateway running",
        "http_temperature_endpoint": "/temperature",
        "mqtt_topic": MQTT_TOPIC_FLAME,
        "udp_port": UDP_PORT,
        "opcua_endpoint": OPCUA_ENDPOINT,
    })


def start_http_server():
    """
    Start the Flask HTTP server.

    This runs in its own thread so that HTTP can work together
    with MQTT, UDP, and OPC UA.
    """

    print(f"[HTTP] Server running on port {HTTP_PORT}")
    app.run(
        host=HTTP_HOST,
        port=HTTP_PORT,
        debug=False,
        use_reloader=False
    )


# =========================================================
# MQTT Subscriber for Flame Sensor
# =========================================================

def on_mqtt_connect(client, userdata, flags, rc):
    """
    This function is called automatically when the gateway connects
    to the MQTT broker.

    Important line:
    client.subscribe(MQTT_TOPIC_FLAME)

    This line makes the Raspberry Pi gateway an MQTT subscriber.
    It subscribes to the topic: factory/flame
    """

    if rc == 0:
        print("[MQTT] Connected to broker")

        # MQTT SUBSCRIBER LINE
        # The gateway listens to messages published on this topic.
        client.subscribe(MQTT_TOPIC_FLAME)

        print("[MQTT] Subscribed to:", MQTT_TOPIC_FLAME)

    else:
        print("[MQTT] Connection failed, rc =", rc)


def on_mqtt_message(client, userdata, msg):
    """
    This function is called automatically whenever a new MQTT message
    arrives on the subscribed topic.

    The flame Arduino is the MQTT publisher.
    The Raspberry Pi gateway is the MQTT subscriber.

    Example incoming MQTT payload:
    {
        "device": "flame_node",
        "flame_raw": 350,
        "flame_detected": true
    }
    """

    try:
        # Convert MQTT payload bytes to text
        payload_text = msg.payload.decode("utf-8")

        # Convert JSON text to Python dictionary
        payload = json.loads(payload_text)

        with lock:
            # Store latest flame sensor values
            data["flame"]["flame_raw"] = safe_int(payload.get("flame_raw"))
            data["flame"]["flame_detected"] = safe_bool(payload.get("flame_detected"))

            # Mark sensor online and update timestamps
            data["flame"]["online"] = True
            data["flame"]["last_update"] = now_string()
            data["flame"]["last_seen"] = time.time()

            # Update flame and overall gateway status
            update_flame_status()
            update_gateway_status()

        print("[MQTT] Flame received:", payload)

    except Exception as e:
        print("[MQTT] Error:", e)


def create_mqtt_client():
    """
    Create MQTT client.

    This includes compatibility for different paho-mqtt versions.
    """

    try:
        # Newer paho-mqtt versions
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION1,
            client_id="raspberry_pi_gateway"
        )
    except Exception:
        # Older paho-mqtt versions
        client = mqtt.Client(client_id="raspberry_pi_gateway")

    return client


def start_mqtt_client():
    """
    Start MQTT subscriber client.

    It connects to the local Mosquitto broker and keeps listening
    to the flame topic forever.

    Important lines:
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message
    client.connect(...)
    client.loop_forever()
    """

    client = create_mqtt_client()

    # Register callback functions
    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    while True:
        try:
            print("[MQTT] Connecting to broker...")

            # Connect to MQTT broker
            client.connect(MQTT_BROKER, MQTT_PORT, 60)

            # Keep MQTT client alive and listening forever
            client.loop_forever()

        except Exception as e:
            print("[MQTT] Broker connection error:", e)
            print("[MQTT] Retrying in 5 seconds...")
            time.sleep(5)


# =========================================================
# UDP Receiver for MPU6050 Vibration Node
# =========================================================

def start_udp_server():
    """
    Start UDP server for vibration data.

    The MPU6050 Arduino sends UDP packets to:
    Raspberry Pi IP, port 6000.

    Important lines:
    socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    -> creates UDP socket

    udp_socket.bind((UDP_HOST, UDP_PORT))
    -> listens on UDP port 6000

    udp_socket.recvfrom(4096)
    -> receives UDP packet
    """

    # Create UDP socket
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Bind socket to Raspberry Pi UDP port
    udp_socket.bind((UDP_HOST, UDP_PORT))

    print(f"[UDP] Listening on port {UDP_PORT}")

    while True:
        try:
            # Receive UDP message
            message, address = udp_socket.recvfrom(4096)

            # Convert UDP bytes to text
            payload_text = message.decode("utf-8").strip()

            # Convert JSON text to Python dictionary
            payload = json.loads(payload_text)

            with lock:
                # Store latest vibration values
                data["vibration"]["accelerometer_available"] = safe_bool(
                    payload.get("accelerometer_available", False)
                )

                data["vibration"]["samples"] = safe_int(payload.get("samples"))

                data["vibration"]["ax"] = safe_float(payload.get("ax"))
                data["vibration"]["ay"] = safe_float(payload.get("ay"))
                data["vibration"]["az"] = safe_float(payload.get("az"))

                data["vibration"]["accel_magnitude"] = safe_float(
                    payload.get("accel_magnitude")
                )

                data["vibration"]["baseline_magnitude"] = safe_float(
                    payload.get("baseline_magnitude")
                )

                data["vibration"]["vibration_rms"] = safe_float(
                    payload.get("vibration_rms")
                )

                data["vibration"]["vibration_g"] = safe_float(
                    payload.get("vibration_g")
                )

                data["vibration"]["vibration_peak"] = safe_float(
                    payload.get("vibration_peak")
                )

                data["vibration"]["magnitude_peak_to_peak"] = safe_float(
                    payload.get("magnitude_peak_to_peak")
                )

                data["vibration"]["vibration_status"] = str(
                    payload.get("vibration_status", "NO_DATA")
                )

                # Mark sensor online and update timestamps
                data["vibration"]["online"] = True
                data["vibration"]["last_update"] = now_string()
                data["vibration"]["last_seen"] = time.time()

                # Vibration node already calculates NORMAL/WARNING/CRITICAL,
                # so here we mainly update the overall gateway status.
                update_gateway_status()

            print("[UDP] Vibration received from", address, ":", payload)

        except Exception as e:
            print("[UDP] Error:", e)


# =========================================================
# OPC UA Server
# =========================================================

def start_opcua_server():
    """
    Start OPC UA server.

    OPC UA is the industrial communication output of this gateway.

    Instead of showing raw HTTP, MQTT, and UDP separately,
    all processed values are exposed in one industrial structure:

    SmartFactory
    ├── TemperatureNode
    ├── FlameNode
    ├── VibrationNode
    └── GatewayProcessedData
    """

    # Create OPC UA server object
    server = Server()

    # Set endpoint address
    server.set_endpoint(OPCUA_ENDPOINT)

    # Set readable server name
    server.set_server_name("Smart Factory Raspberry Pi OPC UA Server")

    # Register custom namespace
    idx = server.register_namespace(OPCUA_NAMESPACE_URI)

    # Get main Objects folder from OPC UA address space
    objects = server.get_objects_node()

    # Create main SmartFactory object
    factory = objects.add_object(idx, "SmartFactory")

    # -----------------------------------------------------
    # Temperature OPC UA Node
    # -----------------------------------------------------

    temp_node = factory.add_object(idx, "TemperatureNode")

    opc_temp_online = temp_node.add_variable(idx, "Online", False)
    opc_temperature = temp_node.add_variable(idx, "Temperature_C", 0.0)
    opc_humidity = temp_node.add_variable(idx, "Humidity_Percent", 0.0)
    opc_temp_status = temp_node.add_variable(idx, "Temperature_Status", "NO_DATA")
    opc_temp_last_update = temp_node.add_variable(idx, "Last_Update", "never")

    # -----------------------------------------------------
    # Flame OPC UA Node
    # -----------------------------------------------------

    flame_node = factory.add_object(idx, "FlameNode")

    opc_flame_online = flame_node.add_variable(idx, "Online", False)
    opc_flame_raw = flame_node.add_variable(idx, "Flame_Raw", 0)
    opc_flame_detected = flame_node.add_variable(idx, "Flame_Detected", False)
    opc_flame_status = flame_node.add_variable(idx, "Flame_Status", "NO_DATA")
    opc_flame_last_update = flame_node.add_variable(idx, "Last_Update", "never")

    # -----------------------------------------------------
    # Vibration OPC UA Node
    # -----------------------------------------------------

    vibration_node = factory.add_object(idx, "VibrationNode")

    opc_vib_online = vibration_node.add_variable(idx, "Online", False)
    opc_acc_available = vibration_node.add_variable(idx, "Accelerometer_Available", False)
    opc_samples = vibration_node.add_variable(idx, "Samples", 0)

    opc_ax = vibration_node.add_variable(idx, "AX_ms2", 0.0)
    opc_ay = vibration_node.add_variable(idx, "AY_ms2", 0.0)
    opc_az = vibration_node.add_variable(idx, "AZ_ms2", 0.0)

    opc_accel_mag = vibration_node.add_variable(
        idx,
        "Acceleration_Magnitude_ms2",
        0.0
    )

    opc_vib_rms = vibration_node.add_variable(idx, "Vibration_RMS_ms2", 0.0)
    opc_vib_g = vibration_node.add_variable(idx, "Vibration_G", 0.0)
    opc_vib_peak = vibration_node.add_variable(idx, "Vibration_Peak_ms2", 0.0)

    opc_vib_p2p = vibration_node.add_variable(
        idx,
        "Magnitude_Peak_To_Peak_ms2",
        0.0
    )

    opc_vib_status = vibration_node.add_variable(
        idx,
        "Vibration_Status",
        "NO_DATA"
    )

    opc_vib_last_update = vibration_node.add_variable(
        idx,
        "Last_Update",
        "never"
    )

    # -----------------------------------------------------
    # Gateway Processed Data OPC UA Node
    # -----------------------------------------------------

    gateway_node = factory.add_object(idx, "GatewayProcessedData")

    opc_overall_status = gateway_node.add_variable(
        idx,
        "Overall_Status",
        "NO_DATA"
    )

    opc_overall_alarm = gateway_node.add_variable(
        idx,
        "Overall_Alarm",
        False
    )

    opc_gateway_last_update = gateway_node.add_variable(
        idx,
        "Last_Update",
        "never"
    )

    # Start OPC UA server
    server.start()

    print("[OPC UA] Server started")
    print("[OPC UA] Endpoint:", OPCUA_ENDPOINT)

    try:
        while True:
            with lock:
                # Before publishing values, check if sensors are still online.
                check_sensor_online_status()

                # -------------------------------------------------
                # Update Temperature OPC UA Variables
                # -------------------------------------------------

                opc_temp_online.set_value(data["temperature"]["online"])
                opc_temperature.set_value(data["temperature"]["temperature_c"])
                opc_humidity.set_value(data["temperature"]["humidity_percent"])
                opc_temp_status.set_value(data["temperature"]["status"])
                opc_temp_last_update.set_value(data["temperature"]["last_update"])

                # -------------------------------------------------
                # Update Flame OPC UA Variables
                # -------------------------------------------------

                opc_flame_online.set_value(data["flame"]["online"])
                opc_flame_raw.set_value(data["flame"]["flame_raw"])
                opc_flame_detected.set_value(data["flame"]["flame_detected"])
                opc_flame_status.set_value(data["flame"]["status"])
                opc_flame_last_update.set_value(data["flame"]["last_update"])

                # -------------------------------------------------
                # Update Vibration OPC UA Variables
                # -------------------------------------------------

                opc_vib_online.set_value(data["vibration"]["online"])
                opc_acc_available.set_value(
                    data["vibration"]["accelerometer_available"]
                )

                opc_samples.set_value(data["vibration"]["samples"])

                opc_ax.set_value(data["vibration"]["ax"])
                opc_ay.set_value(data["vibration"]["ay"])
                opc_az.set_value(data["vibration"]["az"])

                opc_accel_mag.set_value(
                    data["vibration"]["accel_magnitude"]
                )

                opc_vib_rms.set_value(data["vibration"]["vibration_rms"])
                opc_vib_g.set_value(data["vibration"]["vibration_g"])
                opc_vib_peak.set_value(data["vibration"]["vibration_peak"])

                opc_vib_p2p.set_value(
                    data["vibration"]["magnitude_peak_to_peak"]
                )

                opc_vib_status.set_value(
                    data["vibration"]["vibration_status"]
                )

                opc_vib_last_update.set_value(
                    data["vibration"]["last_update"]
                )

                # -------------------------------------------------
                # Update Processed Gateway OPC UA Variables
                # -------------------------------------------------

                opc_overall_status.set_value(
                    data["gateway"]["overall_status"]
                )

                opc_overall_alarm.set_value(
                    data["gateway"]["overall_alarm"]
                )

                opc_gateway_last_update.set_value(
                    data["gateway"]["last_update"]
                )

            # OPC UA values are refreshed once every second.
            time.sleep(1)

    finally:
        server.stop()
        print("[OPC UA] Server stopped")


# =========================================================
# Main Program
# =========================================================

if __name__ == "__main__":
    """
    Main execution starts here.

    The gateway starts:
    - HTTP receiver thread
    - MQTT subscriber thread
    - UDP receiver thread
    - OPC UA server in the main thread

    Why threads?
    Because HTTP, MQTT, UDP, and OPC UA must run at the same time.
    """

    print("==============================================")
    print(" Raspberry Pi Smart Factory OPC UA Gateway")
    print("==============================================")
    print("HTTP temperature receiver :", f"http://<pi-ip>:{HTTP_PORT}/temperature")
    print("MQTT flame topic          :", MQTT_TOPIC_FLAME)
    print("UDP vibration port        :", UDP_PORT)
    print("OPC UA endpoint           :", OPCUA_ENDPOINT)
    print("==============================================")

    # HTTP receiver runs in background
    http_thread = threading.Thread(
        target=start_http_server,
        daemon=True
    )

    # MQTT subscriber runs in background
    mqtt_thread = threading.Thread(
        target=start_mqtt_client,
        daemon=True
    )

    # UDP receiver runs in background
    udp_thread = threading.Thread(
        target=start_udp_server,
        daemon=True
    )

    # Start all background communication threads
    http_thread.start()
    mqtt_thread.start()
    udp_thread.start()

    # Start OPC UA server in main thread
    # This keeps the whole program alive.
    start_opcua_server()