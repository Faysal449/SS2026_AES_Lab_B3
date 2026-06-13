"""
04_erp_live_report.py
ERP / enterprise reporting layer.

Purpose:
- Reads MES and PLC values from OPC UA.
- Creates business-level maintenance/cost decisions.
- Writes ERP values back to OPC UA.
- Generates a constantly updating HTML enterprise report.

Run after 00, 01, and 03:
    python3 04_erp_live_report.py

Open report:
    enterprise_live_report.html
or start a small web server:
    python3 -m http.server 9090
then open:
    http://127.0.0.1:9090/enterprise_live_report.html
"""

import html
import time
from datetime import datetime
from opcua import Client

OPCUA_URL = "opc.tcp://127.0.0.1:4840/factory/server/"
NAMESPACE_URI = "http://smartfactory.local"
REPORT_FILE = "enterprise_live_report.html"
COST_PER_DOWNTIME_MINUTE_EUR = 2.50
OEE_LOW_LIMIT = 60.0


def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_child(parent, idx, name):
    return parent.get_child([f"{idx}:{name}"])


def write_html_report(data):
    status_class = data["business_status"].lower().replace(" ", "-")
    content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="5">
    <title>ERP Enterprise Live Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 30px; background: #f8fafc; color: #111827; }}
        h1 {{ color: #111827; }}
        .box {{ background: white; border: 1px solid #d1d5db; border-radius: 12px; padding: 18px; margin-bottom: 18px; box-shadow: 0 4px 14px rgba(0,0,0,0.08); }}
        .ok {{ color: #047857; font-weight: bold; }}
        .warning {{ color: #b45309; font-weight: bold; }}
        .critical {{ color: #b91c1c; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; background: white; }}
        td, th {{ border: 1px solid #d1d5db; padding: 10px; text-align: left; }}
        th {{ background: #e5e7eb; }}
        .note {{ color: #6b7280; font-size: 14px; }}
    </style>
</head>
<body>
    <h1>ERP Enterprise Live Report</h1>
    <p class="note">Synthetic/simulated report generated from OPC UA data. Auto-refreshes every 5 seconds.</p>

    <div class="box">
        <h2>Business Status: <span class="{status_class}">{html.escape(data['business_status'])}</span></h2>
        <p><b>Last Update:</b> {html.escape(data['timestamp'])}</p>
        <p><b>Maintenance Ticket:</b> {html.escape(data['maintenance_ticket'])}</p>
        <p><b>Spare Part Status:</b> {html.escape(data['spare_part_status'])}</p>
    </div>

    <div class="box">
        <h2>Production and Cost Summary</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Machine State</td><td>{html.escape(data['machine_state'])}</td></tr>
            <tr><td>MES Status</td><td>{html.escape(data['mes_status'])}</td></tr>
            <tr><td>Production Count</td><td>{data['production_count']}</td></tr>
            <tr><td>Good Count</td><td>{data['good_count']}</td></tr>
            <tr><td>Reject Count</td><td>{data['reject_count']}</td></tr>
            <tr><td>Downtime</td><td>{data['downtime_seconds']:.0f} seconds</td></tr>
            <tr><td>Estimated Loss</td><td>{data['estimated_loss_eur']:.2f} €</td></tr>
            <tr><td>Availability</td><td>{data['availability']:.2f} %</td></tr>
            <tr><td>Performance</td><td>{data['performance']:.2f} %</td></tr>
            <tr><td>Quality</td><td>{data['quality']:.2f} %</td></tr>
            <tr><td>OEE</td><td>{data['oee']:.2f} %</td></tr>
        </table>
    </div>

    <div class="box">
        <h2>Enterprise Decision</h2>
        <p>{html.escape(data['enterprise_decision'])}</p>
    </div>
</body>
</html>
"""
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    ticket_counter = 1000

    while True:
        client = Client(OPCUA_URL)
        try:
            print("[04 ERP] Connecting to OPC UA server...")
            client.connect()
            print("[04 ERP] Connected")

            idx = client.get_namespace_index(NAMESPACE_URI)
            smart_factory = get_child(client.nodes.objects, idx, "SmartFactory")
            plc_node = get_child(smart_factory, idx, "PLCControl")
            mes_node = get_child(smart_factory, idx, "MESProduction")
            erp_node = get_child(smart_factory, idx, "ERPBusinessReport")

            machine_state = get_child(plc_node, idx, "Machine_State")
            production_count = get_child(mes_node, idx, "Production_Count")
            good_count = get_child(mes_node, idx, "Good_Count")
            reject_count = get_child(mes_node, idx, "Reject_Count")
            downtime_seconds = get_child(mes_node, idx, "Downtime_Seconds")
            availability = get_child(mes_node, idx, "Availability_Percent")
            performance = get_child(mes_node, idx, "Performance_Percent")
            quality = get_child(mes_node, idx, "Quality_Percent")
            oee = get_child(mes_node, idx, "OEE_Percent")
            mes_status = get_child(mes_node, idx, "MES_Status")

            out_loss = get_child(erp_node, idx, "Estimated_Loss_EUR")
            out_maintenance_required = get_child(erp_node, idx, "Maintenance_Required")
            out_ticket = get_child(erp_node, idx, "Maintenance_Ticket")
            out_spare = get_child(erp_node, idx, "Spare_Part_Status")
            out_business_status = get_child(erp_node, idx, "Business_Status")
            out_erp_update = get_child(erp_node, idx, "ERP_Last_Update")

            while True:
                state = machine_state.get_value()
                prod = int(production_count.get_value())
                good = int(good_count.get_value())
                reject = int(reject_count.get_value())
                downtime = float(downtime_seconds.get_value())
                avail = float(availability.get_value())
                perf = float(performance.get_value())
                qual = float(quality.get_value())
                oee_value = float(oee.get_value())
                mes_stat = mes_status.get_value()

                loss = round((downtime / 60.0) * COST_PER_DOWNTIME_MINUTE_EUR, 2)

                maintenance_required = (
                    "MAINTENANCE" in state
                    or "EMERGENCY" in state
                    or "OVER_TEMPERATURE" in state
                    or oee_value < OEE_LOW_LIMIT
                )

                if maintenance_required:
                    ticket = f"MT-{ticket_counter}"
                    spare = "CHECK_REQUIRED"
                    business_status = "CRITICAL"
                    decision = "Maintenance should be scheduled. Production loss and machine health require attention."
                elif mes_stat == "PRODUCING_WARNING":
                    ticket = "WATCHLIST"
                    spare = "MONITOR"
                    business_status = "WARNING"
                    decision = "Machine is still producing, but process condition should be monitored."
                else:
                    ticket = "NONE"
                    spare = "OK"
                    business_status = "OK"
                    decision = "Machine condition and production performance are acceptable."

                if maintenance_required:
                    ticket_counter += 1

                timestamp = now_string()
                out_loss.set_value(float(loss))
                out_maintenance_required.set_value(bool(maintenance_required))
                out_ticket.set_value(ticket)
                out_spare.set_value(spare)
                out_business_status.set_value(business_status)
                out_erp_update.set_value(timestamp)

                data = {
                    "timestamp": timestamp,
                    "machine_state": state,
                    "mes_status": mes_stat,
                    "production_count": prod,
                    "good_count": good,
                    "reject_count": reject,
                    "downtime_seconds": downtime,
                    "availability": avail,
                    "performance": perf,
                    "quality": qual,
                    "oee": oee_value,
                    "estimated_loss_eur": loss,
                    "maintenance_ticket": ticket,
                    "spare_part_status": spare,
                    "business_status": business_status,
                    "enterprise_decision": decision,
                }
                write_html_report(data)

                print(
                    f"[04 ERP] Business={business_status} | Ticket={ticket} | Loss={loss:.2f} EUR | OEE={oee_value:.2f}% | Report={REPORT_FILE}"
                )
                time.sleep(5)

        except Exception as e:
            print("[04 ERP] Error:", e)
            try:
                client.disconnect()
            except Exception:
                pass
            print("[04 ERP] Reconnecting in 3 seconds...")
            time.sleep(3)


if __name__ == "__main__":
    main()
