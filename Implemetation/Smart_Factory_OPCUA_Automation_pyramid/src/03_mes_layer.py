"""
03_mes_layer.py
MES production layer.

Purpose:
- Reads PLC/machine status from OPC UA.
- Simulates production count and rejects.
- Calculates Availability, Performance, Quality, and OEE.
- Writes MES values back to OPC UA.

Run after 00 and 01. Historian is recommended but not strictly required:
    python3 03_mes_layer.py
"""

import random
import time
from datetime import datetime
from opcua import Client

OPCUA_URL = "opc.tcp://127.0.0.1:4840/factory/server/"
NAMESPACE_URI = "http://smartfactory.local"
IDEAL_PARTS_PER_MINUTE = 12


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_child(parent, idx, name):
    return parent.get_child([f"{idx}:{name}"])


def percent(value):
    return round(max(0.0, min(100.0, value)), 2)


def main():
    production = 0
    good = 0
    reject = 0
    downtime_seconds = 0.0
    planned_runtime_seconds = 0.0

    while True:
        client = Client(OPCUA_URL)
        try:
            print("[03 MES] Connecting to OPC UA server...")
            client.connect()
            print("[03 MES] Connected")

            idx = client.get_namespace_index(NAMESPACE_URI)
            smart_factory = get_child(client.nodes.objects, idx, "SmartFactory")
            plc_node = get_child(smart_factory, idx, "PLCControl")
            gateway_node = get_child(smart_factory, idx, "GatewayProcessedData")
            mes_node = get_child(smart_factory, idx, "MESProduction")

            machine_state = get_child(plc_node, idx, "Machine_State")
            motor_command = get_child(plc_node, idx, "Motor_Command")
            overall_status = get_child(gateway_node, idx, "Overall_Status")

            out_production = get_child(mes_node, idx, "Production_Count")
            out_good = get_child(mes_node, idx, "Good_Count")
            out_reject = get_child(mes_node, idx, "Reject_Count")
            out_downtime = get_child(mes_node, idx, "Downtime_Seconds")
            out_availability = get_child(mes_node, idx, "Availability_Percent")
            out_performance = get_child(mes_node, idx, "Performance_Percent")
            out_quality = get_child(mes_node, idx, "Quality_Percent")
            out_oee = get_child(mes_node, idx, "OEE_Percent")
            out_mes_status = get_child(mes_node, idx, "MES_Status")
            out_mes_update = get_child(mes_node, idx, "MES_Last_Update")

            while True:
                planned_runtime_seconds += 1
                state = machine_state.get_value()
                motor = motor_command.get_value()
                overall = overall_status.get_value()

                running = motor and state in ["RUNNING_NORMAL", "RUNNING_WITH_WARNING"]

                if running:
                    # one second = roughly IDEAL_PARTS_PER_MINUTE / 60 parts
                    # accumulate probabilistically for realistic small-step simulation
                    if random.random() < IDEAL_PARTS_PER_MINUTE / 60.0:
                        production += 1
                        if overall == "WARNING" and random.random() < 0.10:
                            reject += 1
                        else:
                            good += 1
                    mes_status = "PRODUCING_WARNING" if overall == "WARNING" else "PRODUCING_NORMAL"
                else:
                    downtime_seconds += 1
                    mes_status = "DOWNTIME"

                operating_time = planned_runtime_seconds - downtime_seconds
                availability = percent((operating_time / planned_runtime_seconds) * 100.0) if planned_runtime_seconds else 0.0

                ideal_output = (operating_time / 60.0) * IDEAL_PARTS_PER_MINUTE
                performance = percent((production / ideal_output) * 100.0) if ideal_output > 0 else 0.0
                quality = percent((good / production) * 100.0) if production > 0 else 100.0
                oee = round((availability * performance * quality) / 10000.0, 2)

                out_production.set_value(int(production))
                out_good.set_value(int(good))
                out_reject.set_value(int(reject))
                out_downtime.set_value(float(downtime_seconds))
                out_availability.set_value(float(availability))
                out_performance.set_value(float(performance))
                out_quality.set_value(float(quality))
                out_oee.set_value(float(oee))
                out_mes_status.set_value(mes_status)
                out_mes_update.set_value(now_string())

                print(
                    f"[03 MES] Status={mes_status} | Prod={production} Good={good} Reject={reject} | "
                    f"Downtime={downtime_seconds:.0f}s | OEE={oee}%"
                )
                time.sleep(1)

        except Exception as e:
            print("[03 MES] Error:", e)
            try:
                client.disconnect()
            except Exception:
                pass
            print("[03 MES] Reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
