# Smart Factory Full Pyramid Simulation

This folder lets you continue the project after the physical sensors were submitted.
It uses synthetic/simulated data for the same 3 sensors: temperature, flame, and vibration.

## Layers

```text
Level 0: Simulated Sensors
Level 1: OPC UA Gateway + Software PLC
Level 2: SCADA/HMI Dashboard or UaExpert
Historian: SQLite + CSV
Level 3: MES Production Layer
Level 4: ERP Enterprise Report
```

## Install

```bash
python3 -m venv ~/factory_gateway_env
source ~/factory_gateway_env/bin/activate
pip install opcua flask
```

If you already have the environment from the previous dashboard, only run:

```bash
source ~/factory_gateway_env/bin/activate
pip install opcua flask
```

## Run order

Open separate terminals in this folder.

### Terminal 1: simulated OPC UA server

```bash
source ~/factory_gateway_env/bin/activate
python3 00_simulated_opcua_server.py
```

### Terminal 2: software PLC

```bash
source ~/factory_gateway_env/bin/activate
python3 01_software_plc.py
```

### Terminal 3: historian database and CSV

```bash
source ~/factory_gateway_env/bin/activate
python3 02_historian_sqlite.py
```

This constantly updates:

```text
factory_history.db
live_factory_data.csv
```

### Terminal 4: MES production layer

```bash
source ~/factory_gateway_env/bin/activate
python3 03_mes_layer.py
```

### Terminal 5: ERP enterprise report

```bash
source ~/factory_gateway_env/bin/activate
python3 04_erp_live_report.py
```

This constantly updates:

```text
enterprise_live_report.html
```

Open it directly or run:

```bash
python3 -m http.server 9090
```

Then open:

```text
http://127.0.0.1:9090/enterprise_live_report.html
```

## UaExpert

Connect to:

```text
opc.tcp://127.0.0.1:4840/factory/server/
```

Browse:

```text
Objects → SmartFactory
```

You should see:

```text
TemperatureNode
FlameNode
VibrationNode
GatewayProcessedData
PLCControl
MESProduction
ERPBusinessReport
```

## Important academic note

This data is synthetic/simulated. In the report or presentation, say:

"After the real hardware demonstration was completed, a software simulation was used to continue testing the PLC, MES, and ERP layers. The simulated values follow the same OPC UA data structure as the physical sensor implementation."
