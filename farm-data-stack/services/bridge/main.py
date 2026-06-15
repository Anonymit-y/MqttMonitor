import os
import json
import psycopg2
import paho.mqtt.client as mqtt

# Configuration
DB_HOST = os.environ.get('DB_HOST', 'timescaledb')
DB_NAME = os.environ.get('DB_NAME', 'farm_data')
DB_USER = os.environ.get('DB_USER', 'farm_admin')
DB_PASS = os.environ.get('DB_PASS', 'farm_password')

MQTT_BROKER = os.environ.get('MQTT_HOST', 'mosquitto')
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'farm/uplink/#') 
PROFILES_PATH = "/app/sensor_profiles.json"

def get_nested_value(data, path):
    """Safely drills down into a nested dictionary given a list path."""
    current = data
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current

def parse_payload(payload_str):
    """Parses incoming JSON and returns only the metrics based on profiles."""
    try:
        raw_json = json.loads(payload_str)
    except json.JSONDecodeError as e:
        print(f"❌ JSON Decode Error: {e}", flush=True)
        return None, None

    if not os.path.exists(PROFILES_PATH):
        print(f"⚠️ Missing {PROFILES_PATH}", flush=True)
        return None, None

    with open(PROFILES_PATH, 'r') as f:
        profiles = json.load(f).get("profiles", [])

    for profile in profiles:
        temp = get_nested_value(raw_json, profile.get("temperature_path", []))
        hum = get_nested_value(raw_json, profile.get("humidity_path", []))
        
        # If we found the metrics, return them immediately
        if temp is not None and hum is not None:
            return temp, hum

    return None, None

def init_db():
    """Initializes the TimescaleDB table and hypertable."""
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sensor_logs (
            time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            device_id TEXT,
            temperature DOUBLE PRECISION,
            humidity DOUBLE PRECISION
        );
    """)
    # Convert to Hypertable for performance
    cur.execute("SELECT create_hypertable('sensor_logs', 'time', if_not_exists => TRUE);")
    conn.commit()
    cur.close()
    conn.close()
    print("✅ Database table initialized.", flush=True)

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"✅ Connected to Broker! Subscribing to: {MQTT_TOPIC}", flush=True)
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Connection failed: {reason_code}", flush=True)

def on_message(client, userdata, msg):
    print(f"📩 Raw Message on {msg.topic}: {msg.payload.decode()}", flush=True)
    
    # EXTRACT ID FROM TOPIC: splits 'farm/uplink/24e124725d330720' and grabs the last part
    topic_parts = msg.topic.split('/')
    device_id = topic_parts[-1] 

    temp, hum = parse_payload(msg.payload.decode())

    if temp is None or hum is None:
        print("⚠️ No matching profile found for this payload's metrics.", flush=True)
        return

    try:
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO sensor_logs (device_id, temperature, humidity) VALUES (%s, %s, %s)",
            (device_id, temp, hum)
        )
        conn.commit()
        cur.close()
        conn.close()
        print(f"🚀 Logged -> Device: {device_id} | T: {temp}°C | H: {hum}%", flush=True)
    except Exception as e:
        print(f"❌ Database Write Error: {e}", flush=True)

if __name__ == "__main__":
    init_db()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    print(f"🔄 Starting Bridge. Target: {MQTT_BROKER}...", flush=True)
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever()