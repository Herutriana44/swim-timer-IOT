#!/usr/bin/env python3
"""
Test script untuk mengecek koneksi MQTT dengan test.mosquitto.org
"""

import paho.mqtt.client as mqtt
import time
from config_mosquitto import *

def on_connect(client, userdata, flags, rc):
    print(f"✅ Terhubung ke MQTT broker {MQTT_BROKER} dengan code: {rc}")
    if rc == 0:
        print("🎉 Koneksi MQTT ke test.mosquitto.org berhasil!")
        client.subscribe(MQTT_TOPIC)
        print(f"📡 Subscribed ke topic: {MQTT_TOPIC}")
        
        # Subscribe ke wildcard topic untuk melihat semua pesan (hanya 20 detik)
        client.subscribe("#")
        print("🔍 Subscribed ke wildcard topic # (20 detik)")
    else:
        print(f"❌ Gagal koneksi MQTT dengan code: {rc}")

def on_message(client, userdata, msg):
    print(f"📨 Pesan diterima dari topic '{msg.topic}': {msg.payload.decode()}")

def on_disconnect(client, userdata, rc):
    print(f"🔌 Terputus dari MQTT broker {MQTT_BROKER} dengan code: {rc}")

def test_mqtt_connection():
    print("🧪 Testing MQTT Connection dengan test.mosquitto.org...")
    print(f"🌐 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📡 Topic: {MQTT_TOPIC}")
    print(f"ℹ️  Broker Info: {BROKER_INFO['description']}")
    print("-" * 60)
    
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
        client.publish(MQTT_TOPIC, "test_message_from_python")
        client.publish(MQTT_TOPIC, "start")
        time.sleep(1)
        client.publish(MQTT_TOPIC, "stop")
        
        # Wait for messages
        print("⏳ Menunggu pesan (10 detik)...")
        time.sleep(10)
        
        # Test dengan wildcard user (jika tersedia)
        print("🔍 Testing dengan wildcard user...")
        try:
            wildcard_client = mqtt.Client("wildcard_test")
            wildcard_client.on_connect = lambda c, u, f, rc: print(f"Wildcard connect: {rc}")
            wildcard_client.on_message = lambda c, u, msg: print(f"Wildcard message: {msg.topic} -> {msg.payload.decode()}")
            wildcard_client.username_pw_set("wildcard", "")
            wildcard_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            wildcard_client.loop_start()
            wildcard_client.subscribe("#")
            time.sleep(5)
            wildcard_client.loop_stop()
            wildcard_client.disconnect()
        except Exception as e:
            print(f"⚠️  Wildcard test gagal: {e}")
        
        # Stop loop
        client.loop_stop()
        client.disconnect()
        
        print("✅ Test MQTT dengan test.mosquitto.org selesai!")
        print("📋 Hasil test:")
        print(f"   - Broker: {MQTT_BROKER}")
        print(f"   - Port: {MQTT_PORT}")
        print(f"   - Status: Berhasil terhubung")
        print(f"   - Topic: {MQTT_TOPIC}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    return True

def test_different_ports():
    """Test koneksi ke berbagai port yang tersedia"""
    print("\n🔍 Testing berbagai port test.mosquitto.org...")
    
    ports_to_test = [
        (1883, "Unencrypted, unauthenticated"),
        (1884, "Unencrypted, authenticated"),
        (8080, "WebSocket, unencrypted, unauthenticated"),
    ]
    
    for port, description in ports_to_test:
        print(f"\n🧪 Testing port {port} ({description})...")
        try:
            client = mqtt.Client(f"test_port_{port}")
            client.connect(MQTT_BROKER, port, 10)
            print(f"✅ Port {port}: Berhasil")
            client.disconnect()
        except Exception as e:
            print(f"❌ Port {port}: Gagal - {e}")

if __name__ == "__main__":
    print("🏊‍♂️ MQTT Test untuk Swim Timer dengan test.mosquitto.org")
    print("=" * 60)
    
    # Test koneksi utama
    success = test_mqtt_connection()
    
    if success:
        # Test port lain
        test_different_ports()
        
        print("\n🎯 Rekomendasi:")
        print("   - Gunakan port 1883 untuk testing sederhana")
        print("   - Gunakan port 1884 dengan autentikasi untuk keamanan")
        print("   - Gunakan port 8080 untuk WebSocket support")
        print("   - Broker ini cocok untuk testing, bukan production")
    else:
        print("\n❌ Test gagal. Periksa koneksi internet dan konfigurasi.")
