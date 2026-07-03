import paho.mqtt.client as mqtt

BROKER_IP = "192.168.0.10"
PORT = 1883
TOPIC = "test/topic"

def on_message(client, userdata, msg):
    print(f"{msg.topic} {msg.payload.decode()}")

client = mqtt.Client()
client.on_message = on_message

print("Connecting to Raspberry Pi MQTT broker...")
client.connect(BROKER_IP, PORT, 60)

client.subscribe(TOPIC)
print(f"Subscribed to topic: {TOPIC}")
print("Waiting for messages...")

client.loop_forever()