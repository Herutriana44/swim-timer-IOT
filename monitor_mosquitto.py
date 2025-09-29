#!/usr/bin/env python3
"""
Monitor script untuk Swim Timer Web Application dengan test.mosquitto.org
Mengecek status sistem, MQTT connection, dan web interface
"""

import requests
import time
import psutil
import json
from datetime import datetime
from config_mosquitto import *

def check_web_interface():
    """Check apakah web interface berjalan"""
    try:
        response = requests.get(f"http://localhost:{WEB_PORT}", timeout=5)
        if response.status_code == 200:
            return True, "Web interface berjalan normal"
        else:
            return False, f"Web interface error: {response.status_code}"
    except requests.exceptions.RequestException as e:
        return False, f"Web interface tidak dapat diakses: {e}"

def check_mqtt_connection():
    """Check koneksi MQTT ke test.mosquitto.org"""
    try:
        import paho.mqtt.client as mqtt
        
        client = mqtt.Client("monitor_test_mosquitto")
        client.connect(MQTT_BROKER, MQTT_PORT, 5)
        client.disconnect()
        return True, f"MQTT broker {MQTT_BROKER} dapat diakses"
    except Exception as e:
        return False, f"MQTT broker {MQTT_BROKER} tidak dapat diakses: {e}"

def check_system_resources():
    """Check penggunaan resource sistem"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return True, {
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'memory_available': memory.available // (1024**3),  # GB
            'disk_percent': disk.percent,
            'disk_free': disk.free // (1024**3)  # GB
        }
    except Exception as e:
        return False, f"Error checking system resources: {e}"

def check_broker_info():
    """Check informasi broker test.mosquitto.org"""
    try:
        import paho.mqtt.client as mqtt
        
        broker_info = {
            'broker': MQTT_BROKER,
            'port': MQTT_PORT,
            'topic': MQTT_TOPIC,
            'description': BROKER_INFO['description'],
            'features': BROKER_INFO['features'],
            'caveats': BROKER_INFO['caveats']
        }
        
        return True, broker_info
    except Exception as e:
        return False, f"Error getting broker info: {e}"

def test_mqtt_publish_subscribe():
    """Test publish dan subscribe ke MQTT broker"""
    try:
        import paho.mqtt.client as mqtt
        import threading
        import time
        
        received_messages = []
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                client.subscribe(MQTT_TOPIC)
                print(f"✅ Subscribed ke {MQTT_TOPIC}")
            else:
                print(f"❌ MQTT connect failed: {rc}")
        
        def on_message(client, userdata, msg):
            received_messages.append({
                'topic': msg.topic,
                'message': msg.payload.decode(),
                'timestamp': datetime.now().strftime('%H:%M:%S')
            })
        
        # Create client
        client = mqtt.Client("monitor_test_pubsub")
        client.on_connect = on_connect
        client.on_message = on_message
        
        # Connect and test
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # Wait for connection
        time.sleep(2)
        
        # Publish test message
        test_message = f"monitor_test_{int(time.time())}"
        client.publish(MQTT_TOPIC, test_message)
        print(f"📤 Published test message: {test_message}")
        
        # Wait for message
        time.sleep(3)
        
        client.loop_stop()
        client.disconnect()
        
        return True, received_messages
        
    except Exception as e:
        return False, f"MQTT test failed: {e}"

def generate_report():
    """Generate monitoring report"""
    print("🏊‍♂️ Swim Timer Monitor - test.mosquitto.org")
    print("=" * 60)
    print(f"⏰ Waktu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📡 Topic: {MQTT_TOPIC}")
    print("-" * 60)
    
    # Check web interface
    print("🌐 Checking Web Interface...")
    web_ok, web_msg = check_web_interface()
    if web_ok:
        print(f"✅ {web_msg}")
    else:
        print(f"❌ {web_msg}")
    
    # Check MQTT connection
    print("\n📡 Checking MQTT Connection...")
    mqtt_ok, mqtt_msg = check_mqtt_connection()
    if mqtt_ok:
        print(f"✅ {mqtt_msg}")
    else:
        print(f"❌ {mqtt_msg}")
    
    # Check system resources
    print("\n💻 Checking System Resources...")
    sys_ok, sys_data = check_system_resources()
    if sys_ok:
        print(f"✅ CPU: {sys_data['cpu_percent']:.1f}%")
        print(f"✅ Memory: {sys_data['memory_percent']:.1f}% ({sys_data['memory_available']} GB available)")
        print(f"✅ Disk: {sys_data['disk_percent']:.1f}% ({sys_data['disk_free']} GB free)")
    else:
        print(f"❌ {sys_data}")
    
    # Check broker info
    print("\nℹ️  Broker Information...")
    broker_ok, broker_data = check_broker_info()
    if broker_ok:
        print(f"✅ Broker: {broker_data['broker']}")
        print(f"✅ Port: {broker_data['port']}")
        print(f"✅ Description: {broker_data['description']}")
        print("✅ Features:")
        for feature in broker_data['features']:
            print(f"   - {feature}")
        print("⚠️  Caveats:")
        for caveat in broker_data['caveats']:
            print(f"   - {caveat}")
    else:
        print(f"❌ {broker_data}")
    
    # Test MQTT publish/subscribe
    print("\n🧪 Testing MQTT Publish/Subscribe...")
    test_ok, test_data = test_mqtt_publish_subscribe()
    if test_ok:
        print(f"✅ MQTT test berhasil")
        if test_data:
            print("📨 Messages received:")
            for msg in test_data:
                print(f"   [{msg['timestamp']}] {msg['topic']}: {msg['message']}")
        else:
            print("⚠️  No messages received (normal for test)")
    else:
        print(f"❌ {test_data}")
    
    print("\n" + "=" * 60)
    
    # Summary
    all_ok = web_ok and mqtt_ok and sys_ok and broker_ok and test_ok
    if all_ok:
        print("🎉 Semua sistem berjalan normal!")
    else:
        print("⚠️  Beberapa masalah terdeteksi. Periksa log di atas.")
    
    return all_ok

def continuous_monitor(interval=30):
    """Monitor berkelanjutan"""
    print(f"🔄 Starting continuous monitor (interval: {interval}s)")
    print("Tekan Ctrl+C untuk berhenti")
    
    try:
        while True:
            generate_report()
            print(f"\n⏳ Menunggu {interval} detik...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n🛑 Monitor dihentikan oleh user")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--continuous":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        continuous_monitor(interval)
    else:
        generate_report()
