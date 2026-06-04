# SS2026_AES_Lab_B3

## Smart Factory Condition Monitoring using Raspberry Pi, Arduino, MQTT, UDP, HTTP and OPC UA

This project implements a small smart-factory condition monitoring system. Multiple Arduino-based sensor nodes send data to a Raspberry Pi using different communication protocols. The Raspberry Pi works as an industrial gateway: it collects raw sensor data, processes it, converts it into structured OPC UA variables, and exposes the data to an industrial client or dashboard.

The final system demonstrates how heterogeneous IoT sensor data can be converted into an industrial dashboard-compatible format using OPC UA.

---

## Project Overview

The system uses three sensor nodes:

| Sensor Node      | Sensor Type   | Communication Protocol | Data Sent                                  |
| ---------------- | ------------- | ---------------------- | ------------------------------------------ |
| Temperature Node | DHT11         | HTTP POST              | Temperature and humidity                   |
| Flame Node       | Flame sensor  | MQTT                   | Flame raw value and flame detection status |
| Vibration Node   | MPU6050 / IMU | UDP                    | Acceleration and vibration data            |

The Raspberry Pi receives all sensor values and publishes them as OPC UA variables. These values can be monitored using UaExpert, Node-RED, SCADA tools, or the custom web dashboard.

---

## System Architecture

```text
+---------------------+       HTTP POST        +-----------------------------+
| Arduino DHT11 Node  | ---------------------> |                             |
| Temperature/Humidity|                        |                             |
+---------------------+                        |                             |
                                                 |                             |
+---------------------+       MQTT             |     Raspberry Pi Gateway     |
| Arduino Flame Node  | ---------------------> |                             |
| Flame Detection     |                        |                             |
+---------------------+                        |                             |
                                                 |                             |
+---------------------+       UDP              |                             |
| Arduino IMU Node    | ---------------------> |                             |
| Vibration Monitoring|                        +--------------+--------------+
+---------------------+                                       |
                                                              |
                                                              | OPC UA
                                                              |
                                                              v
                                            +----------------------------------+
                                            | Industrial Client / Dashboard    |
                                            | UaExpert / Node-RED / Web UI     |
                                            +----------------------------------+
```

---

## Main Features

* Receives temperature and humidity data through HTTP.
* Receives flame sensor data through MQTT.
* Receives IMU/vibration data through UDP.
* Converts raw sensor values into structured OPC UA variables.
* Provides industrial-style status processing:

  * `NORMAL`
  * `WARNING`
  * `CRITICAL`
  * `ALARM`
* Provides an OPC UA server for industrial clients.
* Provides a web dashboard for visual monitoring.
* Demonstrates Raspberry Pi as an IoT-to-Industrial gateway.

---

## Repository Structure

```text
SS2026_AES_Lab_B3
│
├── Implementation
│   │
│   ├── Arduino_to_raspberry_pi
│   │   ├── http_temperature_sensor
│   │   ├── mqtt_flame_sensor
│   │   └── udp_imu_sensor
│   │
│   ├── opcua_industrial_interface
│   │   ├── opcua_gateway.py
│   │   └── industrial_dashboard.py
│   │
│   └── Results
│       ├── Raw_data.png
│       ├── OpcUa_converted_data.png
│       └── Dashboard.png
│
├── seminar_paper
│
└── README.md
```

---

## Hardware Used

* Raspberry Pi
* Arduino Uno WiFi / Arduino WiFiNINA compatible board
* DHT11 temperature and humidity sensor
* Flame sensor
* MPU6050 IMU sensor
* WiFi hotspot or local WiFi network

---

## Software and Libraries

### Raspberry Pi

* Python 3
* Flask
* Paho MQTT
* python-opcua
* Mosquitto MQTT broker

### Arduino

* WiFiNINA library
* DHT library
* PubSubClient library
* WiFiUdp library
* Wire library

### Client / Monitoring

* UaExpert OPC UA client
* Web browser for dashboard

---

## Communication Protocols

### 1. HTTP for Temperature Sensor

The DHT11 Arduino node sends temperature and humidity data to the Raspberry Pi using HTTP POST.

Example payload:

```json
{
  "device": "dht11_node",
  "temperature_c": 22.0,
  "humidity_percent": 63.0
}
```

Endpoint on Raspberry Pi:

```text
http://<raspberry_pi_ip>:5000/temperature
```

---

### 2. MQTT for Flame Sensor

The flame sensor node publishes data to the Raspberry Pi MQTT broker.

MQTT topic:

```text
factory/flame
```

Example payload:

```json
{
  "device": "flame_node",
  "flame_raw": 795,
  "flame_detected": false
}
```

---

### 3. UDP for IMU / Vibration Sensor

The MPU6050 node sends vibration data to the Raspberry Pi using UDP.

UDP port:

```text
6000
```

Example payload:

```json
{
  "device": "vibration_node",
  "accelerometer_available": true,
  "samples": 50,
  "ax": -3.516,
  "ay": 7.857,
  "az": 3.419,
  "accel_magnitude": 9.262,
  "vibration_rms": 0.043,
  "vibration_g": 0.0044,
  "vibration_status": "NORMAL"
}
```

---

## Raspberry Pi Setup

Install required packages:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv mosquitto mosquitto-clients
```

Start and enable Mosquitto:

```bash
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

Create a Python virtual environment:

```bash
python3 -m venv ~/factory_gateway_env
source ~/factory_gateway_env/bin/activate
```

Install Python libraries:

```bash
pip install flask paho-mqtt opcua
```

---

## Running the OPC UA Gateway

Go to the OPC UA interface folder:

```bash
cd Implementation/opcua_industrial_interface
```

Activate the Python environment:

```bash
source ~/factory_gateway_env/bin/activate
```

Run the gateway:

```bash
python3 opcua_gateway.py
```

Expected terminal output:

```text
[HTTP] Server running on port 5000
[MQTT] Connected to broker
[UDP] Listening on port 6000
[OPC UA] Server started
```

When sensor data is received, the terminal shows:

```text
[HTTP] Temperature received
[MQTT] Flame received
[UDP] Vibration received
```

---

## OPC UA Server

The Raspberry Pi exposes the industrial data through OPC UA.

OPC UA endpoint:

```text
opc.tcp://<raspberry_pi_ip>:4840/factory/server/
```

Example:

```text
opc.tcp://10.153.76.64:4840/factory/server/
```

---

## OPC UA Node Structure

The OPC UA client can browse the following node structure:

```text
Objects
└── SmartFactory
    ├── TemperatureNode
    │   ├── Online
    │   ├── Temperature_C
    │   ├── Humidity_Percent
    │   ├── Temperature_Status
    │   └── Last_Update
    │
    ├── FlameNode
    │   ├── Online
    │   ├── Flame_Raw
    │   ├── Flame_Detected
    │   ├── Flame_Status
    │   └── Last_Update
    │
    ├── VibrationNode
    │   ├── Online
    │   ├── Accelerometer_Available
    │   ├── AX_ms2
    │   ├── AY_ms2
    │   ├── AZ_ms2
    │   ├── Vibration_RMS_ms2
    │   ├── Vibration_G
    │   ├── Vibration_Status
    │   └── Last_Update
    │
    └── GatewayProcessedData
        ├── Overall_Status
        ├── Overall_Alarm
        └── Last_Update
```

---

## UaExpert Connection

To connect using UaExpert:

1. Open UaExpert.
2. Add a new server.
3. Use custom discovery.
4. Enter the OPC UA endpoint:

```text
opc.tcp://<raspberry_pi_ip>:4840/factory/server/
```

Example:

```text
opc.tcp://10.153.76.64:4840/factory/server/
```

Use the following settings:

```text
Security Policy: None
Message Security Mode: None
Authentication: Anonymous
```

After connecting, browse:

```text
Objects → SmartFactory
```

Then drag the required variables into the Data Access View.

---

## Running the Industrial Dashboard

The dashboard reads data from the OPC UA server and shows it in a browser-based industrial interface.

Go to the OPC UA interface folder:

```bash
cd Implementation/opcua_industrial_interface
```

Activate the environment:

```bash
source ~/factory_gateway_env/bin/activate
```

Run the dashboard:

```bash
python3 industrial_dashboard.py
```

Open the dashboard in a browser:

```text
http://<raspberry_pi_ip>:8080/dashboard
```

Example:

```text
http://10.153.76.64:8080/dashboard
```

---

## Dashboard View

The dashboard displays:

* Overall system status
* Overall alarm condition
* Temperature value
* Humidity value
* Flame raw value
* Flame detection status
* Vibration RMS
* Vibration status
* OPC UA connection status
* Last update time

Example dashboard values:

```text
Temperature        : 22.0 °C
Humidity           : 63.0 %
Temperature Status : NORMAL

Flame Raw          : 592
Flame Detected     : False
Flame Status       : NORMAL

Vibration RMS      : 0.806 m/s²
Vibration Status   : CRITICAL

Overall Status     : CRITICAL
Overall Alarm      : True
```

---

## Result Screenshots

### Raw Sensor Data

![Raw Sensor Data](Implementation/Results/Raw_data.png)

### OPC UA Converted Data

![OPC UA Converted Data](Implementation/Results/OpcUa_converted_data.png)

### Industrial Dashboard

![Industrial Dashboard](Implementation/Results/Dashboard.png)

---

## Status Processing Logic

The Raspberry Pi gateway processes raw sensor data and generates industrial status values.

### Temperature Status

```text
NORMAL   → temperature and humidity are within normal range
WARNING  → temperature or humidity is high
CRITICAL → temperature is too high
```

### Flame Status

```text
NORMAL → no flame detected
ALARM  → flame detected
```

### Vibration Status

```text
NORMAL   → low vibration
WARNING  → medium vibration
CRITICAL → high vibration
```

### Overall Status

```text
NORMAL   → all sensor nodes are normal
WARNING  → one or more sensors show warning or no data
CRITICAL → flame alarm, critical temperature, or critical vibration detected
```

---

## Demonstration Flow

1. Start the Raspberry Pi gateway.
2. Run the Arduino temperature, flame, and IMU sensor nodes.
3. Verify that the Raspberry Pi receives HTTP, MQTT, and UDP data.
4. Connect UaExpert to the Raspberry Pi OPC UA endpoint.
5. Browse the `SmartFactory` OPC UA node tree.
6. Run the industrial dashboard.
7. Trigger sensor changes and observe live status updates.

---

## Purpose of OPC UA in This Project

OPC UA is used to convert sensor-level IoT communication into an industrial data interface. The Arduino nodes use simple communication methods such as HTTP, MQTT, and UDP. The Raspberry Pi hides this protocol complexity and exposes all data in a structured OPC UA format.

This allows industrial clients, dashboards, or SCADA systems to read the data in a standardized way.

---

## Conclusion

This project demonstrates a Raspberry Pi-based industrial IoT gateway. It receives data from multiple Arduino sensor nodes using different protocols, processes the data, and exposes it through OPC UA for industrial dashboard usage.

The system successfully shows the complete flow:

```text
Sensor Nodes → Raspberry Pi Gateway → OPC UA Server → Industrial Dashboard
```
