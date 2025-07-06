#!/usr/bin/env python3
"""
Test script untuk mengecek koneksi MQTT
"""

import paho.mqtt.client as mqtt
import time
from config import *

def on_connect(client, userdata, flags, rc):
    print(f"✅ Terhubung ke MQTT broker dengan code: {rc}")
    if rc == 0:
        print("🎉 Koneksi MQTT berhasil!")
        client.subscribe(MQTT_TOPIC)
        print(f"📡 Subscribed ke topic: {MQTT_TOPIC}")
    else:
        print(f"❌ Gagal koneksi MQTT dengan code: {rc}")

def on_message(client, userdata, msg):
    print(f"📨 Pesan diterima dari topic '{msg.topic}': {msg.payload.decode()}")

def on_disconnect(client, userdata, rc):
    print(f"🔌 Terputus dari MQTT broker dengan code: {rc}")

def test_mqtt_connection():
    print("🧪 Testing MQTT Connection...")
    print(f"🌐 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📡 Topic: {MQTT_TOPIC}")
    print("-" * 50)
    
    # Create MQTT client
    client = mqtt.Client(MQTT_CLIENT_ID + "_test")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        # Connect to broker
        print("🔗 Menghubungkan ke MQTT broker...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Start loop
        client.loop_start()
        
        # Wait for connection
        time.sleep(3)
        
        # Test publish
        print("📤 Testing publish message...")
        client.publish(MQTT_TOPIC, "test_message")
        
        # Wait for message
        print("⏳ Menunggu pesan...")
        time.sleep(5)
        
        # Stop loop
        client.loop_stop()
        client.disconnect()
        
        print("✅ Test MQTT selesai!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    test_mqtt_connection() 