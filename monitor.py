#!/usr/bin/env python3
"""
Monitoring script untuk Swim Timer Web Application
"""

import requests
import json
import time
import os
from datetime import datetime

def check_web_interface():
    """Check apakah web interface berjalan"""
    try:
        response = requests.get('http://localhost:5000/api/timer', timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, data
        else:
            return False, None
    except requests.exceptions.RequestException:
        return False, None

def check_mqtt_connection():
    """Check koneksi MQTT"""
    try:
        import paho.mqtt.client as mqtt
        from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC
        
        client = mqtt.Client("monitor_test")
        client.connect(MQTT_BROKER, MQTT_PORT, 5)
        client.disconnect()
        return True
    except Exception:
        return False

def check_system_resources():
    """Check penggunaan resource sistem"""
    try:
        # CPU usage
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[0]
        
        # Memory usage
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            total_mem = int(lines[0].split()[1])
            free_mem = int(lines[1].split()[1])
            used_mem = total_mem - free_mem
            mem_percent = (used_mem / total_mem) * 100
        
        # Disk usage
        stat = os.statvfs('/')
        total_disk = stat.f_blocks * stat.f_frsize
        free_disk = stat.f_bavail * stat.f_frsize
        used_disk = total_disk - free_disk
        disk_percent = (used_disk / total_disk) * 100
        
        return {
            'cpu_load': float(load),
            'memory_percent': round(mem_percent, 1),
            'disk_percent': round(disk_percent, 1)
        }
    except Exception:
        return None

def main():
    print("🔍 Swim Timer System Monitor")
    print("=" * 50)
    
    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n📅 {timestamp}")
        print("-" * 30)
        
        # Check web interface
        web_running, timer_data = check_web_interface()
        if web_running:
            print("✅ Web Interface: Running")
            if timer_data:
                print(f"   ⏱️ Timer: {timer_data.get('time', 'N/A')}")
                print(f"   🏃 Status: {'Running' if timer_data.get('running') else 'Stopped'}")
                print(f"   🏊 Lap Count: {timer_data.get('lap_count', 0)}")
        else:
            print("❌ Web Interface: Not Running")
        
        # Check MQTT
        mqtt_ok = check_mqtt_connection()
        if mqtt_ok:
            print("✅ MQTT Connection: OK")
        else:
            print("❌ MQTT Connection: Failed")
        
        # Check system resources
        resources = check_system_resources()
        if resources:
            print(f"💻 CPU Load: {resources['cpu_load']}")
            print(f"🧠 Memory Usage: {resources['memory_percent']}%")
            print(f"💾 Disk Usage: {resources['disk_percent']}%")
        
        # Check service status
        try:
            result = os.system("systemctl is-active --quiet swim-timer.service")
            if result == 0:
                print("✅ System Service: Active")
            else:
                print("❌ System Service: Inactive")
        except:
            print("⚠️  System Service: Unknown")
        
        print("\n⏳ Waiting 10 seconds...")
        time.sleep(10)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Monitor stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}") 