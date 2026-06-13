import os
import json
import psycopg2
import paho.mqtt.client as mqtt

# Configuration from Environment Variables
DB_HOST = os.environ.get('DB_HOST', 'timescaledb')
DB_NAME = os.environ.get('DB_NAME', 'farm_data')
DB_USER = os.environ.get('DB_USER', 'farm_admin')
DB_PASS = os.environ.get('DB_PASS', 'farm_password')
MQTT_BROKER = os.environ.get('MQTT_HOST', 'mosquitto')
MQTT_TOPIC = os.environ.get('MQTT_TOPIC', 'application/+/event/up')
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

def parse_payload_with_profiles(payload_str):
    """Matches the raw string payload against known sensor profiles."""
    # Fix potential single quote formatting issues from raw payloads
    clean_str = payload_str.replace("'", '"')
    raw_json = json.loads(clean_str)

    # Reload profiles dynamically on each message so updates don't require restarts
    if os.path.exists(PROFILES_PATH):
        with open(PROFILES_PATH, 'r') as f:
            config = json.load(f)
            profiles = config.get("profiles", [])
    else:
        print(f"⚠️ Profile file not found at {PROFILES_PATH}! Using empty profiles.", flush=True)
        profiles = []

    # Iterate through profiles to find a match where data matches expected structural paths
    for profile in profiles:
        dev_id = get_nested_value(raw_json, profile.get("device_id_path", []))
        
        if dev_id is not None:
            temp = get_nested_value(raw_json, profile.get("temperature_path", []))
            hum = get_nested_value(raw_json, profile.get("humidity_path", []))
            return str(dev_id), temp, hum

    return None, None, None

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"✅ Connected to MQTT Broker! Subscribing to: {MQTT_TOPIC}", flush=True)
        client.subscribe(MQTT_TOPIC)
    else:
        print(f"❌ Connection failed with reason code: {reason_code}", flush=True)

def on_message(client, userdata, msg):
    payload_str = msg.payload.decode('utf-8')
    print(f"📩 Incoming on {msg.topic}: {payload_str}", flush=True)
    
    conn = None
    try:
        device_id, temp, hum = parse_payload_with_profiles(payload_str)

        if device_id is None:
            print("⚠️ Payload did not match any known profile signatures. Skipping.", flush=True)
            return

        if temp is None or hum is None:
            print(f"⚠️ Matched device {device_id}, but metrics were missing. Skipping DB insert.", flush=True)
            return

        # Open short-lived connection to TimescaleDB
        conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()

        # Ensure the hypertable/standard table exists before inserting
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sensor_logs (
                time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                device_id TEXT,
                temperature DOUBLE PRECISION,
                humidity DOUBLE PRECISION
            );
        """)

        query = "INSERT INTO sensor_logs (device_id, temperature, humidity) VALUES (%s, %s, %s)"
        cur.execute(query, (device_id, temp, hum))
        
        conn.commit()
        cur.close()
        print(f"🚀 Successfully Logged -> Device: {device_id} | Temp: {temp}°C | Hum: {hum}%", flush=True)

    except Exception as e:
        print(f"❌ Error processing message: {e}", flush=True)
    finally:
        if conn:
            conn.close()

# Initialize MQTT Client using standard Callback API v2
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

try:
    print(f"🔄 Starting Bridge. Connecting to {MQTT_BROKER}...", flush=True)
    client.connect(MQTT_BROKER, 1883, 60)
    client.loop_forever()
except KeyboardInterrupt:
    print("🛑 Bridge stopped manually.", flush=True)
except Exception as e:
    print(f"💥 Fatal Exception: {e}", flush=True)
