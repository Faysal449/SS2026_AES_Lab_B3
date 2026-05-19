# Industrial IoT-Based Smart Factory Condition Monitoring System with MQTT and OPC UA

## Project Overview

This project is developed for the **Advanced Embedded Systems** course.  
The goal is to build a small **Smart Factory Condition Monitoring System** using **Raspberry Pi, Arduino sensor nodes, MQTT, and OPC UA**.

The project uses different sensors such as temperature, ultrasonic, light/LDR, and moisture sensors to monitor the condition of a simulated industrial environment. The sensor data is collected by Arduino nodes and sent to a Raspberry Pi gateway. The Raspberry Pi processes the data, logs it, displays it, and exposes the values through an OPC UA interface.

This project is also connected to our **seminar paper on OPC UA**, where we study OPC UA as an industrial communication standard. Therefore, the practical project demonstrates how OPC UA can be used in a real embedded/IoT smart factory scenario.

---

## Since our seminar paper focuses on OPC UA, we are integrating OPC UA into this project to demonstrate how the theoretical concept can be applied in a practical smart factory monitoring system.

In this project:

- **MQTT** is used for lightweight IoT communication between Arduino sensor nodes and the Raspberry Pi.
- **OPC UA** is used as an industrial communication interface so that the Raspberry Pi can provide sensor data to industrial clients such as UaExpert, Node-RED, or SCADA-like systems.

This makes the project relevant for **embedded systems**, **industrial automation**, **IoT**, and **smart factory applications**.

---

## System Architecture

```text
Arduino Sensor Nodes
Temperature / Light / Moisture / Ultrasonic
        |
        | MQTT
        v
Raspberry Pi Gateway
- MQTT Subscriber
- Data Processing
- Threshold Logic
- Data Logging
- Dashboard
        |
        | OPC UA Server
        v
Industrial Client
UaExpert / Node-RED / SCADA-like System

##Sensors Required

For this project, the following sensors and hardware components are required:

Raspberry Pi
Arduino
Temperature sensor
Ultrasonic sensor
LDR / light sensor
Moisture sensor
Breadboard
