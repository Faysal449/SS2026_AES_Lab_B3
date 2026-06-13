"""
00_simulated_opcua_server.py
Synthetic Smart Factory OPC UA server.

Purpose:
- Replaces real Arduino sensors after hardware submission.
- Generates synthetic temperature, flame, and vibration data every second.
- Publishes the same SmartFactory OPC UA structure used by the dashboard.
- Creates writable PLC, MES, and ERP nodes for upper layers.

Run first:
    python3 00_simulated_opcua_server.py
"""

import random
import time
from datetime import datetime
from opcua import Server

OPCUA_ENDPOINT = "opc.tcp://0.0.0.0:4840/factory/server/"
NAMESPACE_URI = "http://smartfactory.local"


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def temperature_status(temp_c, humidity_percent):
    if temp_c >= 45:
        return "CRITICAL"
    if temp_c >= 35 or humidity_percent >= 80:
        return "WARNING"
    return "NORMAL"


def flame_status(flame_detected):
    return "ALARM" if flame_detected else "NORMAL"


def vibration_status(vibration_rms):
    if vibration_rms < 0.25:
        return "NORMAL"
    if vibration_rms < 0.80:
        return "WARNING"
    return "CRITICAL"


def gateway_status(temp_status, flame_status_value, vib_status):
    if temp_status == "CRITICAL" or flame_status_value == "ALARM" or vib_status == "CRITICAL":
        return "CRITICAL", True
    if temp_status == "WARNING" or vib_status == "WARNING":
        return "WARNING", False
    return "NORMAL", False


def generate_sensor_values():
    """Generate realistic synthetic factory sensor values."""
    mode = random.choices(
        ["NORMAL", "TEMP_WARNING", "TEMP_CRITICAL", "VIB_WARNING", "VIB_CRITICAL", "FLAME_ALARM"],
        weights=[62, 9, 4, 10, 10, 5],
        k=1,
    )[0]

    temp_c = random.uniform(21.0, 28.0)
    humidity = random.uniform(45.0, 68.0)
    flame_raw = random.randint(700, 980)
    flame_detected = False
    vibration_rms = random.uniform(0.04, 0.22)

    if mode == "TEMP_WARNING":
        temp_c = random.uniform(35.0, 42.0)
        humidity = random.uniform(72.0, 88.0)
    elif mode == "TEMP_CRITICAL":
        temp_c = random.uniform(45.0, 55.0)
        humidity = random.uniform(70.0, 90.0)
    elif mode == "VIB_WARNING":
        vibration_rms = random.uniform(0.30, 0.75)
    elif mode == "VIB_CRITICAL":
        vibration_rms = random.uniform(0.90, 1.80)
    elif mode == "FLAME_ALARM":
        flame_raw = random.randint(80, 350)
        flame_detected = True

    vibration_g = vibration_rms / 9.80665
    temp_stat = temperature_status(temp_c, humidity)
    flame_stat = flame_status(flame_detected)
    vib_stat = vibration_status(vibration_rms)
    overall_stat, overall_alarm = gateway_status(temp_stat, flame_stat, vib_stat)

    return {
        "mode": mode,
        "time": now_string(),
        "temperature_c": round(temp_c, 1),
        "humidity_percent": round(humidity, 1),
        "temperature_status": temp_stat,
        "flame_raw": flame_raw,
        "flame_detected": flame_detected,
        "flame_status": flame_stat,
        "vibration_rms": round(vibration_rms, 3),
        "vibration_g": round(vibration_g, 4),
        "vibration_status": vib_stat,
        "overall_status": overall_stat,
        "overall_alarm": overall_alarm,
    }


def make_writable(*nodes):
    for node in nodes:
        node.set_writable()


def main():
    server = Server()
    server.set_endpoint(OPCUA_ENDPOINT)
    server.set_server_name("Smart Factory Synthetic Pyramid OPC UA Server")

    idx = server.register_namespace(NAMESPACE_URI)
    objects = server.get_objects_node()
    factory = objects.add_object(idx, "SmartFactory")

    # Level 0/1: field data exposed by gateway
    temp_node = factory.add_object(idx, "TemperatureNode")
    temp_online = temp_node.add_variable(idx, "Online", True)
    temperature = temp_node.add_variable(idx, "Temperature_C", 0.0)
    humidity = temp_node.add_variable(idx, "Humidity_Percent", 0.0)
    temp_status = temp_node.add_variable(idx, "Temperature_Status", "NO_DATA")
    temp_update = temp_node.add_variable(idx, "Last_Update", "never")

    flame_node = factory.add_object(idx, "FlameNode")
    flame_online = flame_node.add_variable(idx, "Online", True)
    flame_raw = flame_node.add_variable(idx, "Flame_Raw", 0)
    flame_detected = flame_node.add_variable(idx, "Flame_Detected", False)
    flame_stat = flame_node.add_variable(idx, "Flame_Status", "NO_DATA")
    flame_update = flame_node.add_variable(idx, "Last_Update", "never")

    vib_node = factory.add_object(idx, "VibrationNode")
    vib_online = vib_node.add_variable(idx, "Online", True)
    acc_available = vib_node.add_variable(idx, "Accelerometer_Available", True)
    samples = vib_node.add_variable(idx, "Samples", 50)
    ax = vib_node.add_variable(idx, "AX_ms2", 0.0)
    ay = vib_node.add_variable(idx, "AY_ms2", 0.0)
    az = vib_node.add_variable(idx, "AZ_ms2", 9.81)
    accel_mag = vib_node.add_variable(idx, "Acceleration_Magnitude_ms2", 9.81)
    vib_rms = vib_node.add_variable(idx, "Vibration_RMS_ms2", 0.0)
    vib_g = vib_node.add_variable(idx, "Vibration_G", 0.0)
    vib_peak = vib_node.add_variable(idx, "Vibration_Peak_ms2", 0.0)
    vib_p2p = vib_node.add_variable(idx, "Magnitude_Peak_To_Peak_ms2", 0.0)
    vib_status = vib_node.add_variable(idx, "Vibration_Status", "NO_DATA")
    vib_update = vib_node.add_variable(idx, "Last_Update", "never")

    gateway_node = factory.add_object(idx, "GatewayProcessedData")
    overall_status = gateway_node.add_variable(idx, "Overall_Status", "NO_DATA")
    overall_alarm = gateway_node.add_variable(idx, "Overall_Alarm", False)
    gateway_update = gateway_node.add_variable(idx, "Last_Update", "never")

    # Level 1: software PLC output
    plc_node = factory.add_object(idx, "PLCControl")
    machine_state = plc_node.add_variable(idx, "Machine_State", "STARTING")
    motor_command = plc_node.add_variable(idx, "Motor_Command", False)
    fan_command = plc_node.add_variable(idx, "Fan_Command", False)
    buzzer_command = plc_node.add_variable(idx, "Buzzer_Command", False)
    emergency_stop = plc_node.add_variable(idx, "Emergency_Stop", False)
    plc_decision = plc_node.add_variable(idx, "PLC_Last_Decision", "Waiting for PLC")
    plc_update = plc_node.add_variable(idx, "PLC_Last_Update", "never")
    make_writable(machine_state, motor_command, fan_command, buzzer_command, emergency_stop, plc_decision, plc_update)

    # Level 3: MES output
    mes_node = factory.add_object(idx, "MESProduction")
    production_count = mes_node.add_variable(idx, "Production_Count", 0)
    good_count = mes_node.add_variable(idx, "Good_Count", 0)
    reject_count = mes_node.add_variable(idx, "Reject_Count", 0)
    downtime_seconds = mes_node.add_variable(idx, "Downtime_Seconds", 0.0)
    availability = mes_node.add_variable(idx, "Availability_Percent", 0.0)
    performance = mes_node.add_variable(idx, "Performance_Percent", 0.0)
    quality = mes_node.add_variable(idx, "Quality_Percent", 0.0)
    oee = mes_node.add_variable(idx, "OEE_Percent", 0.0)
    mes_status = mes_node.add_variable(idx, "MES_Status", "NO_DATA")
    mes_update = mes_node.add_variable(idx, "MES_Last_Update", "never")
    make_writable(production_count, good_count, reject_count, downtime_seconds, availability, performance, quality, oee, mes_status, mes_update)

    # Level 4: ERP output
    erp_node = factory.add_object(idx, "ERPBusinessReport")
    estimated_loss_eur = erp_node.add_variable(idx, "Estimated_Loss_EUR", 0.0)
    maintenance_required = erp_node.add_variable(idx, "Maintenance_Required", False)
    maintenance_ticket = erp_node.add_variable(idx, "Maintenance_Ticket", "NONE")
    spare_part_status = erp_node.add_variable(idx, "Spare_Part_Status", "OK")
    business_status = erp_node.add_variable(idx, "Business_Status", "NO_DATA")
    erp_update = erp_node.add_variable(idx, "ERP_Last_Update", "never")
    make_writable(estimated_loss_eur, maintenance_required, maintenance_ticket, spare_part_status, business_status, erp_update)

    server.start()
    print("[00 SERVER] Synthetic OPC UA server started")
    print("[00 SERVER] Endpoint:", OPCUA_ENDPOINT)
    print("[00 SERVER] Use CTRL+C to stop")

    try:
        while True:
            d = generate_sensor_values()

            temp_online.set_value(True)
            temperature.set_value(d["temperature_c"])
            humidity.set_value(d["humidity_percent"])
            temp_status.set_value(d["temperature_status"])
            temp_update.set_value(d["time"])

            flame_online.set_value(True)
            flame_raw.set_value(d["flame_raw"])
            flame_detected.set_value(d["flame_detected"])
            flame_stat.set_value(d["flame_status"])
            flame_update.set_value(d["time"])

            vib_online.set_value(True)
            acc_available.set_value(True)
            samples.set_value(50)
            ax.set_value(round(random.uniform(-1.5, 1.5), 3))
            ay.set_value(round(random.uniform(-1.5, 1.5), 3))
            az.set_value(round(random.uniform(8.8, 10.2), 3))
            accel_mag.set_value(round(random.uniform(9.0, 10.5), 3))
            vib_rms.set_value(d["vibration_rms"])
            vib_g.set_value(d["vibration_g"])
            vib_peak.set_value(round(d["vibration_rms"] * 1.8, 3))
            vib_p2p.set_value(round(d["vibration_rms"] * 2.5, 3))
            vib_status.set_value(d["vibration_status"])
            vib_update.set_value(d["time"])

            overall_status.set_value(d["overall_status"])
            overall_alarm.set_value(d["overall_alarm"])
            gateway_update.set_value(d["time"])

            print(
                f"[SENSOR SIM] {d['mode']:<14} | "
                f"T={d['temperature_c']:>4}C {d['temperature_status']:<8} | "
                f"Flame={str(d['flame_detected']):<5} {d['flame_status']:<6} | "
                f"Vib={d['vibration_rms']:<5} {d['vibration_status']:<8} | "
                f"Overall={d['overall_status']}"
            )
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[00 SERVER] Stopping...")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
