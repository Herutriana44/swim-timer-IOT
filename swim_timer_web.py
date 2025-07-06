#!/usr/bin/env python3
"""
Swim Timer Web Application untuk Raspberry Pi 3
Menampilkan timer renang secara realtime dari ESP32 sensors
"""

import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
import json

app = Flask(__name__)

# Global variables untuk timer
timer_running = False
start_time = None
elapsed_time = timedelta(0)
last_lap_time = None
lap_count = 0

# Import configuration
from config import *

# MQTT Configuration (from config.py)
# MQTT_BROKER, MQTT_PORT, MQTT_TOPIC already imported

def on_connect(client, userdata, flags, rc):
    """Callback ketika terhubung ke MQTT broker"""
    print(f"Terhubung ke MQTT broker dengan code: {rc}")
    client.subscribe(MQTT_TOPIC)
    print(f"Subscribed ke topic: {MQTT_TOPIC}")

def on_message(client, userdata, msg):
    """Callback ketika menerima pesan MQTT"""
    global timer_running, start_time, elapsed_time, last_lap_time, lap_count
    
    message = msg.payload.decode('utf-8').strip()
    print(f"Pesan diterima: {message}")
    
    if message == "start":
        if not timer_running:
            timer_running = True
            start_time = datetime.now()
            elapsed_time = timedelta(0)
            lap_count = 0
            print("Timer STARTED")
        else:
            # Lap time
            if start_time:
                current_time = datetime.now()
                last_lap_time = current_time - start_time
                lap_count += 1
                print(f"Lap {lap_count}: {last_lap_time}")
    
    elif message == "stop":
        if timer_running:
            timer_running = False
            if start_time:
                elapsed_time = datetime.now() - start_time
            print(f"Timer STOPPED. Total time: {elapsed_time}")

def update_timer():
    """Thread untuk update timer secara realtime"""
    global elapsed_time
    
    while True:
        if timer_running and start_time:
            elapsed_time = datetime.now() - start_time
        time.sleep(TIMER_UPDATE_INTERVAL)  # Update berdasarkan konfigurasi

def start_mqtt_client():
    """Start MQTT client dalam thread terpisah"""
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"Error koneksi MQTT: {e}")

@app.route('/')
def index():
    """Halaman utama web interface"""
    return render_template('index.html')

@app.route('/api/timer')
def get_timer_data():
    """API endpoint untuk data timer (AJAX)"""
    global timer_running, elapsed_time, last_lap_time, lap_count
    
    # Format waktu untuk display
    if timer_running and start_time:
        current_elapsed = datetime.now() - start_time
        display_time = str(current_elapsed).split('.')[0]  # Hapus microseconds
    else:
        display_time = str(elapsed_time).split('.')[0]
    
    # Format lap time
    lap_display = ""
    if last_lap_time:
        lap_display = str(last_lap_time).split('.')[0]
    
    return jsonify({
        'running': timer_running,
        'time': display_time,
        'lap_count': lap_count,
        'lap_time': lap_display
    })

@app.route('/api/reset')
def reset_timer():
    """API endpoint untuk reset timer"""
    global timer_running, start_time, elapsed_time, last_lap_time, lap_count
    
    timer_running = False
    start_time = None
    elapsed_time = timedelta(0)
    last_lap_time = None
    lap_count = 0
    
    return jsonify({'status': 'reset'})

if __name__ == '__main__':
    # Start MQTT client dalam thread terpisah
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()
    
    # Start timer update thread
    timer_thread = threading.Thread(target=update_timer, daemon=True)
    timer_thread.start()
    
    print("Swim Timer Web Application starting...")
    print("MQTT Topic:", MQTT_TOPIC)
    print("Web interface akan tersedia di: http://localhost:5000")
    
    # Start Flask web server
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG) 