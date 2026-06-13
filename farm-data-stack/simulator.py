import paho.mqtt.client as mqtt
import time
import random
import json

# EXACT configuration to match your docker-compose bridge settings
MQTT_BROKER = "localhost" 
MQTT_TOPIC = "application/device1/event/up" # Must match the bridge pattern

def generate_data():
    return {
        "devEUI": "0011223344556677",
        "data": {
            "temperature": round(random.uniform(20.0, 30.0), 2),
            "humidity": round(random.uniform(40.0, 60.0), 2),
            "battery": round(random.uniform(80.0, 100.0), 2)
        }
    }

def run_simulator():
    # Using the newer API style to avoid the DeprecationWarning you saw
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    
    try:
        print(f"Connecting to broker: {MQTT_BROKER}...")
        client.connect(MQTT_BROKER, 1883, 60)
        client.loop_start()
        print("Connected! Sending data...")

        while True:
            payload = generate_data()
            payload_str = str(payload) # Bridge usually expects string or json
            
            print(f"Publishing: {payload_str}")
            client.publish(MQTT_TOPIC, payload_str)

            time.sleep(5)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    run_simulator()