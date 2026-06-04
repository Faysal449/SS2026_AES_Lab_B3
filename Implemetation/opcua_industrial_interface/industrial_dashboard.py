cd ~
source ~/factory_gateway_env/bin/activate

cat > industrial_dashboard.py <<'PY'
import threading
import time
from flask import Flask, jsonify, render_template_string
from opcua import Client

OPCUA_URL = "opc.tcp://127.0.0.1:4840/factory/server/"
NAMESPACE_URI = "http://smartfactory.local"

app = Flask(__name__)

latest_data = {
    "connected": False,
    "temperature_c": 0.0,
    "humidity_percent": 0.0,
    "temperature_status": "NO_DATA",
    "flame_raw": 0,
    "flame_detected": False,
    "flame_status": "NO_DATA",
    "vibration_rms": 0.0,
    "vibration_g": 0.0,
    "vibration_status": "NO_DATA",
    "overall_status": "NO_DATA",
    "overall_alarm": False,
    "last_update": "Waiting..."
}


def opcua_reader():
    global latest_data

    while True:
        client = Client(OPCUA_URL)

        try:
            client.connect()
            print("[DASHBOARD] Connected to OPC UA server")

            idx = client.get_namespace_index(NAMESPACE_URI)
            objects = client.nodes.objects

            smart_factory = objects.get_child([f"{idx}:SmartFactory"])

            temp_node = smart_factory.get_child([f"{idx}:TemperatureNode"])
            flame_node = smart_factory.get_child([f"{idx}:FlameNode"])
            vib_node = smart_factory.get_child([f"{idx}:VibrationNode"])
            gateway_node = smart_factory.get_child([f"{idx}:GatewayProcessedData"])

            temperature = temp_node.get_child([f"{idx}:Temperature_C"])
            humidity = temp_node.get_child([f"{idx}:Humidity_Percent"])
            temp_status = temp_node.get_child([f"{idx}:Temperature_Status"])

            flame_raw = flame_node.get_child([f"{idx}:Flame_Raw"])
            flame_detected = flame_node.get_child([f"{idx}:Flame_Detected"])
            flame_status = flame_node.get_child([f"{idx}:Flame_Status"])

            vibration_rms = vib_node.get_child([f"{idx}:Vibration_RMS_ms2"])
            vibration_g = vib_node.get_child([f"{idx}:Vibration_G"])
            vibration_status = vib_node.get_child([f"{idx}:Vibration_Status"])

            overall_status = gateway_node.get_child([f"{idx}:Overall_Status"])
            overall_alarm = gateway_node.get_child([f"{idx}:Overall_Alarm"])
            last_update = gateway_node.get_child([f"{idx}:Last_Update"])

            while True:
                latest_data = {
                    "connected": True,
                    "temperature_c": temperature.get_value(),
                    "humidity_percent": humidity.get_value(),
                    "temperature_status": temp_status.get_value(),
                    "flame_raw": flame_raw.get_value(),
                    "flame_detected": flame_detected.get_value(),
                    "flame_status": flame_status.get_value(),
                    "vibration_rms": vibration_rms.get_value(),
                    "vibration_g": vibration_g.get_value(),
                    "vibration_status": vibration_status.get_value(),
                    "overall_status": overall_status.get_value(),
                    "overall_alarm": overall_alarm.get_value(),
                    "last_update": last_update.get_value()
                }

                time.sleep(1)

        except Exception as e:
            print("[DASHBOARD] OPC UA error:", e)
            latest_data["connected"] = False
            latest_data["last_update"] = "OPC UA disconnected"

            try:
                client.disconnect()
            except Exception:
                pass

            time.sleep(3)


@app.route("/api/data")
def api_data():
    return jsonify(latest_data)


@app.route("/")
@app.route("/dashboard")
def dashboard():
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
    <title>Smart Factory Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #0f172a;
            color: white;
        }

        .header {
            background: #1e293b;
            padding: 22px;
            text-align: center;
            border-bottom: 3px solid #334155;
        }

        .header h1 {
            margin: 0;
            font-size: 32px;
        }

        .header p {
            margin: 8px 0 0;
            color: #cbd5e1;
        }

        .container {
            padding: 25px;
        }

        .overall {
            padding: 22px;
            border-radius: 14px;
            text-align: center;
            font-size: 30px;
            font-weight: bold;
            margin-bottom: 25px;
        }

        .NORMAL {
            background: #047857;
        }

        .WARNING {
            background: #b45309;
        }

        .CRITICAL, .ALARM {
            background: #b91c1c;
            animation: blink 1s infinite;
        }

        .NO_DATA {
            background: #475569;
        }

        @keyframes blink {
            50% { opacity: 0.65; }
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
        }

        .card {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0px 8px 25px rgba(0,0,0,0.3);
        }

        .card h2 {
            margin-top: 0;
            color: #93c5fd;
        }

        .big {
            font-size: 38px;
            font-weight: bold;
            margin: 10px 0;
        }

        .medium {
            font-size: 24px;
            font-weight: bold;
            margin: 8px 0 18px;
        }

        .label {
            color: #cbd5e1;
            font-size: 15px;
        }

        .true {
            color: #f87171;
        }

        .false {
            color: #34d399;
        }

        .footer {
            margin-top: 25px;
            text-align: center;
            color: #94a3b8;
        }
    </style>
</head>

<body>
    <div class="header">
        <h1>Smart Factory Condition Monitoring Dashboard</h1>
        <p>OPC UA Client View | Raspberry Pi Industrial Gateway</p>
    </div>

    <div class="container">
        <div id="overallBox" class="overall NO_DATA">
            Overall Status: Loading...
        </div>

        <div class="grid">
            <div class="card">
                <h2>Temperature Node</h2>

                <div class="label">Temperature</div>
                <div class="big"><span id="temperature">--</span> °C</div>

                <div class="label">Humidity</div>
                <div class="medium"><span id="humidity">--</span> %</div>

                <div class="label">Status</div>
                <div class="medium" id="tempStatus">--</div>
            </div>

            <div class="card">
                <h2>Flame Node</h2>

                <div class="label">Flame Raw Value</div>
                <div class="big" id="flameRaw">--</div>

                <div class="label">Flame Detected</div>
                <div class="medium" id="flameDetected">--</div>

                <div class="label">Status</div>
                <div class="medium" id="flameStatus">--</div>
            </div>

            <div class="card">
                <h2>Vibration Node</h2>

                <div class="label">Vibration RMS</div>
                <div class="big"><span id="vibrationRms">--</span> m/s²</div>

                <div class="label">Vibration G</div>
                <div class="medium"><span id="vibrationG">--</span> g</div>

                <div class="label">Status</div>
                <div class="medium" id="vibrationStatus">--</div>
            </div>

            <div class="card">
                <h2>Gateway Alarm</h2>

                <div class="label">Overall Alarm</div>
                <div class="big" id="overallAlarm">--</div>

                <div class="label">OPC UA Connection</div>
                <div class="medium" id="connection">--</div>

                <div class="label">Last Update</div>
                <div class="medium" id="lastUpdate">--</div>
            </div>
        </div>

        <div class="footer">
            Sensor Input: HTTP + MQTT + UDP | Industrial Output: OPC UA
        </div>
    </div>

<script>
async function updateDashboard() {
    const response = await fetch("/api/data");
    const data = await response.json();

    document.getElementById("temperature").innerText = Number(data.temperature_c).toFixed(1);
    document.getElementById("humidity").innerText = Number(data.humidity_percent).toFixed(1);
    document.getElementById("tempStatus").innerText = data.temperature_status;

    document.getElementById("flameRaw").innerText = data.flame_raw;
    document.getElementById("flameDetected").innerText = data.flame_detected;
    document.getElementById("flameStatus").innerText = data.flame_status;

    document.getElementById("vibrationRms").innerText = Number(data.vibration_rms).toFixed(3);
    document.getElementById("vibrationG").innerText = Number(data.vibration_g).toFixed(4);
    document.getElementById("vibrationStatus").innerText = data.vibration_status;

    document.getElementById("overallAlarm").innerText = data.overall_alarm;
    document.getElementById("overallAlarm").className = data.overall_alarm ? "big true" : "big false";

    document.getElementById("connection").innerText = data.connected ? "Connected" : "Disconnected";
    document.getElementById("lastUpdate").innerText = data.last_update;

    let status = data.overall_status;
    let box = document.getElementById("overallBox");

    box.innerText = "Overall Status: " + status;
    box.className = "overall " + status;
}

setInterval(updateDashboard, 1000);
updateDashboard();
</script>

</body>
</html>
    """)


if __name__ == "__main__":
    t = threading.Thread(target=opcua_reader, daemon=True)
    t.start()

    print("Dashboard running at:")
    print("http://0.0.0.0:8080/dashboard")

    app.run(host="0.0.0.0", port=8080, debug=False)
PY
