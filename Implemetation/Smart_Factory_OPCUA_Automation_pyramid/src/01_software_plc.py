"""
01_software_plc.py
Software PLC layer.

Purpose:
- Reads synthetic sensor/gateway values from OPC UA.
- Makes control decisions like a PLC.
- Writes machine/actuator commands back to OPC UA.

Run after 00_simulated_opcua_server.py:
    python3 01_software_plc.py
"""

import time
from datetime import datetime
from opcua import Client

OPCUA_URL = "opc.tcp://127.0.0.1:4840/factory/server/"
NAMESPACE_URI = "http://smartfactory.local"


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_child(parent, idx, name):
    return parent.get_child([f"{idx}:{name}"])


def main():
    while True:
        client = Client(OPCUA_URL)
        try:
            print("[01 PLC] Connecting to OPC UA server...")
            client.connect()
            print("[01 PLC] Connected")

            idx = client.get_namespace_index(NAMESPACE_URI)
            smart_factory = get_child(client.nodes.objects, idx, "SmartFactory")

            temp_node = get_child(smart_factory, idx, "TemperatureNode")
            flame_node = get_child(smart_factory, idx, "FlameNode")
            vib_node = get_child(smart_factory, idx, "VibrationNode")
            gateway_node = get_child(smart_factory, idx, "GatewayProcessedData")
            plc_node = get_child(smart_factory, idx, "PLCControl")

            temperature = get_child(temp_node, idx, "Temperature_C")
            temp_status = get_child(temp_node, idx, "Temperature_Status")
            flame_detected = get_child(flame_node, idx, "Flame_Detected")
            flame_status = get_child(flame_node, idx, "Flame_Status")
            vibration_rms = get_child(vib_node, idx, "Vibration_RMS_ms2")
            vibration_status = get_child(vib_node, idx, "Vibration_Status")
            overall_status = get_child(gateway_node, idx, "Overall_Status")
            overall_alarm = get_child(gateway_node, idx, "Overall_Alarm")

            machine_state = get_child(plc_node, idx, "Machine_State")
            motor_command = get_child(plc_node, idx, "Motor_Command")
            fan_command = get_child(plc_node, idx, "Fan_Command")
            buzzer_command = get_child(plc_node, idx, "Buzzer_Command")
            emergency_stop = get_child(plc_node, idx, "Emergency_Stop")
            plc_decision = get_child(plc_node, idx, "PLC_Last_Decision")
            plc_update = get_child(plc_node, idx, "PLC_Last_Update")

            while True:
                temp = temperature.get_value()
                t_status = temp_status.get_value()
                flame = flame_detected.get_value()
                f_status = flame_status.get_value()
                vib = vibration_rms.get_value()
                v_status = vibration_status.get_value()
                g_status = overall_status.get_value()
                alarm = overall_alarm.get_value()

                if flame or f_status == "ALARM":
                    state = "EMERGENCY_STOP_FLAME"
                    motor = False
                    fan = False
                    buzzer = True
                    estop = True
                    decision = "Flame alarm: stop motor, buzzer ON, emergency stop active."

                elif v_status == "CRITICAL":
                    state = "STOPPED_MAINTENANCE_REQUIRED"
                    motor = False
                    fan = False
                    buzzer = True
                    estop = False
                    decision = "Critical vibration: stop motor and request maintenance."

                elif t_status == "CRITICAL":
                    state = "STOPPED_OVER_TEMPERATURE"
                    motor = False
                    fan = True
                    buzzer = True
                    estop = False
                    decision = "Critical temperature: stop motor and turn fan ON."

                elif t_status == "WARNING" or v_status == "WARNING":
                    state = "RUNNING_WITH_WARNING"
                    motor = True
                    fan = t_status == "WARNING"
                    buzzer = False
                    estop = False
                    decision = "Warning only: continue running with monitoring."

                else:
                    state = "RUNNING_NORMAL"
                    motor = True
                    fan = False
                    buzzer = False
                    estop = False
                    decision = "Normal condition: machine running."

                machine_state.set_value(state)
                motor_command.set_value(motor)
                fan_command.set_value(fan)
                buzzer_command.set_value(buzzer)
                emergency_stop.set_value(estop)
                plc_decision.set_value(decision)
                plc_update.set_value(now_string())

                print("-" * 80)
                print(f"[01 PLC INPUT]  T={temp}C/{t_status} | Flame={flame}/{f_status} | Vib={vib}/{v_status} | Overall={g_status}/{alarm}")
                print(f"[01 PLC OUTPUT] State={state} | Motor={motor} | Fan={fan} | Buzzer={buzzer} | EStop={estop}")
                print(f"[01 PLC DECISION] {decision}")

                time.sleep(1)

        except Exception as e:
            print("[01 PLC] Error:", e)
            try:
                client.disconnect()
            except Exception:
                pass
            print("[01 PLC] Reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
