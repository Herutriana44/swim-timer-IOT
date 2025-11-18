#!/usr/bin/env python3
"""
Swim Timer Web Application untuk Raspberry Pi 3 dengan 2 Lintasan
Menampilkan timer renang secara realtime dari ESP32 sensors untuk 2 lintasan

KONFIGURASI:
-----------
Untuk menggunakan dengan kode Arduino yang ada:
- Semua device menggunakan topic yang sama: "renang/timer"
- Lintasan 1 timerstart mengirim: "start2"
- Lintasan 2 timerstart mengirim: "start2"
- Lintasan 1 timerstop mengirim: "stop"
- Lintasan 2 timerstop mengirim: "stop"

CARA KERJA:
-----------
1. Jika menggunakan topic terpisah (disarankan):
   - Set MQTT_TOPIC_LANE1 = "renang/timer/lintasan1"
   - Set MQTT_TOPIC_LANE2 = "renang/timer/lintasan2"
   - Update kode Arduino untuk menggunakan topic yang sesuai

2. Jika menggunakan topic yang sama (current Arduino code):
   - Sistem akan menggunakan heuristik untuk membedakan lintasan
   - "start2" akan diberikan ke lintasan yang tidak sedang running
   - "stop" akan diberikan ke lintasan yang sedang running

API ENDPOINTS:
-------------
- GET  /api/timer          - Data semua lintasan
- GET  /api/timer/1        - Data lintasan 1
- GET  /api/timer/2        - Data lintasan 2
- POST /api/reset          - Reset semua lintasan
- POST /api/reset/1        - Reset lintasan 1
- POST /api/reset/2        - Reset lintasan 2
"""

import paho.mqtt.client as mqtt
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify
import json

app = Flask(__name__)

# Struktur data untuk setiap lintasan
class LaneTimer:
    def __init__(self, lane_number):
        self.lane_number = lane_number
        self.timer_running = False
        self.start_time = None
        self.elapsed_time = timedelta(0)
        self.last_lap_time = None
        self.lap_count = 0
        self.finished = False

# Global variables untuk 2 lintasan
lanes = {
    1: LaneTimer(1),
    2: LaneTimer(2)
}

# Import configuration dari config_mosquitto.py
try:
    from config_mosquitto import *
except ImportError:
    # Default configuration jika config_mosquitto.py tidak ada
    MQTT_BROKER = "broker.emqx.io"
    MQTT_PORT = 1883
    MQTT_TOPIC = "renang/timer"
    MQTT_CLIENT_ID = "swim_timer_web"
    TIMER_UPDATE_INTERVAL = 0.1
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 5000
    WEB_DEBUG = False
    BROKER_INFO = {"name": "EMQX", "url": MQTT_BROKER}

# Topic untuk setiap lintasan (bisa menggunakan topic terpisah atau sama)
MQTT_TOPIC_LANE1 = getattr(globals(), 'MQTT_TOPIC_LANE1', MQTT_TOPIC)
MQTT_TOPIC_LANE2 = getattr(globals(), 'MQTT_TOPIC_LANE2', MQTT_TOPIC)

def on_connect(client, userdata, flags, rc):
    """Callback ketika terhubung ke MQTT broker"""
    print(f"Terhubung ke MQTT broker {MQTT_BROKER} dengan code: {rc}")
    if rc == 0:
        print("✅ Koneksi MQTT berhasil!")
        # Subscribe ke topic untuk kedua lintasan
        client.subscribe(MQTT_TOPIC_LANE1)
        client.subscribe(MQTT_TOPIC_LANE2)
        print(f"📡 Subscribed ke topic Lintasan 1: {MQTT_TOPIC_LANE1}")
        print(f"📡 Subscribed ke topic Lintasan 2: {MQTT_TOPIC_LANE2}")
    else:
        print(f"❌ Gagal koneksi MQTT dengan code: {rc}")

def on_message(client, userdata, msg):
    """Callback ketika menerima pesan MQTT"""
    global lanes
    
    message = msg.payload.decode('utf-8').strip()
    topic = msg.topic
    
    # Tentukan lintasan berdasarkan topic
    lane_num = None
    
    # Jika topic berbeda, gunakan topic untuk identifikasi
    if MQTT_TOPIC_LANE1 != MQTT_TOPIC_LANE2:
        if topic == MQTT_TOPIC_LANE1:
            lane_num = 1
        elif topic == MQTT_TOPIC_LANE2:
            lane_num = 2
    else:
        # Jika topic sama, gunakan heuristik untuk menentukan lintasan
        # Strategi: Cari lintasan yang sedang running atau yang paling baru menerima pesan
        # Untuk "start2": gunakan lintasan yang tidak sedang running
        # Untuk "stop": gunakan lintasan yang sedang running
        
        if message == "start2":
            # Cari lintasan yang tidak sedang running
            if not lanes[1].timer_running:
                lane_num = 1
            elif not lanes[2].timer_running:
                lane_num = 2
            else:
                # Jika keduanya running, gunakan lintasan dengan waktu start lebih lama (untuk lap)
                if lanes[1].start_time and lanes[2].start_time:
                    lane_num = 1 if lanes[1].start_time <= lanes[2].start_time else 2
                else:
                    lane_num = 1  # Default
        elif message == "stop":
            # Cari lintasan yang sedang running
            if lanes[1].timer_running:
                lane_num = 1
            elif lanes[2].timer_running:
                lane_num = 2
            else:
                # Jika tidak ada yang running, coba dari yang paling baru selesai
                if lanes[1].finished and lanes[2].finished:
                    lane_num = 1  # Default ke lintasan 1
                elif lanes[1].finished:
                    lane_num = 1
                elif lanes[2].finished:
                    lane_num = 2
                else:
                    lane_num = 1  # Default
        elif message == "stop2":
            # stop2 biasanya untuk reset, cari lintasan yang sedang running atau finished
            if lanes[1].timer_running or lanes[1].finished:
                lane_num = 1
            elif lanes[2].timer_running or lanes[2].finished:
                lane_num = 2
            else:
                lane_num = 1  # Default
        else:
            lane_num = 1  # Default untuk pesan lain
    
    if lane_num is None:
        lane_num = 1  # Fallback
    
    lane = lanes[lane_num]
    
    print(f"📨 Pesan diterima dari topic {topic} (Lintasan {lane_num}): {message}")
    
    # Handle pesan "start2" dari timerstart devices
    if message == "start2":
        if not lane.timer_running:
            lane.timer_running = True
            lane.start_time = datetime.now()
            lane.elapsed_time = timedelta(0)
            lane.lap_count = 0
            lane.finished = False
            print(f"🏊‍♂️ Lintasan {lane_num} - Timer STARTED")
        else:
            # Lap time (jika timer sudah running)
            if lane.start_time:
                current_time = datetime.now()
                lane.last_lap_time = current_time - lane.start_time
                lane.lap_count += 1
                print(f"🏁 Lintasan {lane_num} - Lap {lane.lap_count}: {lane.last_lap_time}")
    
    # Handle pesan "stop" dari timerstop devices
    elif message == "stop":
        if lane.timer_running:
            lane.timer_running = False
            lane.finished = True
            if lane.start_time:
                lane.elapsed_time = datetime.now() - lane.start_time
            print(f"⏹️ Lintasan {lane_num} - Timer STOPPED. Total time: {lane.elapsed_time}")
    
    # Handle pesan "stop2" untuk reset (dari timerstart ketika menerima stop2)
    elif message == "stop2":
        lane.timer_running = False
        lane.finished = True
        if lane.start_time:
            lane.elapsed_time = datetime.now() - lane.start_time
        print(f"🔄 Lintasan {lane_num} - Timer RESET (stop2 diterima)")
    
    # Handle pesan "reset" manual
    elif message == "reset":
        lane.timer_running = False
        lane.start_time = None
        lane.elapsed_time = timedelta(0)
        lane.last_lap_time = None
        lane.lap_count = 0
        lane.finished = False
        print(f"🔄 Lintasan {lane_num} - Timer di-reset manual")

def on_disconnect(client, userdata, rc):
    """Callback ketika terputus dari MQTT broker"""
    print(f"🔌 Terputus dari MQTT broker {MQTT_BROKER} dengan code: {rc}")

def update_timer():
    """Thread untuk update timer secara realtime untuk semua lintasan"""
    global lanes
    
    while True:
        for lane_num, lane in lanes.items():
            if lane.timer_running and lane.start_time:
                lane.elapsed_time = datetime.now() - lane.start_time
        time.sleep(TIMER_UPDATE_INTERVAL)

def start_mqtt_client():
    """Start MQTT client dalam thread terpisah"""
    client = mqtt.Client(MQTT_CLIENT_ID + "_web_2lanes")
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    
    try:
        print(f"🔗 Menghubungkan ke MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_forever()
    except Exception as e:
        print(f"❌ Error koneksi MQTT ke {MQTT_BROKER}: {e}")

@app.route('/')
def index():
    """Halaman utama web interface"""
    return render_template('index.html')

@app.route('/api/timer')
def get_timer_data():
    """API endpoint untuk data timer semua lintasan (AJAX)"""
    global lanes
    
    result = {}
    for lane_num, lane in lanes.items():
        # Format waktu untuk display
        if lane.timer_running and lane.start_time:
            current_elapsed = datetime.now() - lane.start_time
            display_time = str(current_elapsed).split('.')[0]  # Hapus microseconds
        else:
            display_time = str(lane.elapsed_time).split('.')[0]
        
        # Format lap time
        lap_display = ""
        if lane.last_lap_time:
            lap_display = str(lane.last_lap_time).split('.')[0]
        
        result[f'lane_{lane_num}'] = {
            'running': lane.timer_running,
            'time': display_time,
            'lap_count': lane.lap_count,
            'lap_time': lap_display,
            'finished': lane.finished
        }
    
    result['broker'] = MQTT_BROKER
    return jsonify(result)

@app.route('/api/timer/<int:lane_num>')
def get_timer_data_lane(lane_num):
    """API endpoint untuk data timer lintasan tertentu"""
    global lanes
    
    if lane_num not in lanes:
        return jsonify({'error': 'Lane not found'}), 404
    
    lane = lanes[lane_num]
    
    # Format waktu untuk display
    if lane.timer_running and lane.start_time:
        current_elapsed = datetime.now() - lane.start_time
        display_time = str(current_elapsed).split('.')[0]
    else:
        display_time = str(lane.elapsed_time).split('.')[0]
    
    # Format lap time
    lap_display = ""
    if lane.last_lap_time:
        lap_display = str(lane.last_lap_time).split('.')[0]
    
    return jsonify({
        'lane': lane_num,
        'running': lane.timer_running,
        'time': display_time,
        'lap_count': lane.lap_count,
        'lap_time': lap_display,
        'finished': lane.finished,
        'broker': MQTT_BROKER
    })

@app.route('/api/reset')
def reset_timer():
    """API endpoint untuk reset semua timer"""
    global lanes
    
    for lane_num, lane in lanes.items():
        lane.timer_running = False
        lane.start_time = None
        lane.elapsed_time = timedelta(0)
        lane.last_lap_time = None
        lane.lap_count = 0
        lane.finished = False
    
    print("🔄 Semua timer di-reset")
    return jsonify({'status': 'reset', 'lanes': [1, 2]})

@app.route('/api/reset/<int:lane_num>')
def reset_timer_lane(lane_num):
    """API endpoint untuk reset timer lintasan tertentu"""
    global lanes
    
    if lane_num not in lanes:
        return jsonify({'error': 'Lane not found'}), 404
    
    lane = lanes[lane_num]
    lane.timer_running = False
    lane.start_time = None
    lane.elapsed_time = timedelta(0)
    lane.last_lap_time = None
    lane.lap_count = 0
    lane.finished = False
    
    print(f"🔄 Timer Lintasan {lane_num} di-reset")
    return jsonify({'status': 'reset', 'lane': lane_num})

@app.route('/api/broker-info')
def get_broker_info():
    """API endpoint untuk informasi broker"""
    return jsonify(BROKER_INFO)

if __name__ == '__main__':
    print("🏊‍♂️ Swim Timer Web Application - 2 Lintasan")
    print(f"🌐 Broker: {MQTT_BROKER}:{MQTT_PORT}")
    print(f"📡 Topic Lintasan 1: {MQTT_TOPIC_LANE1}")
    print(f"📡 Topic Lintasan 2: {MQTT_TOPIC_LANE2}")
    print("-" * 50)
    
    # Start MQTT client dalam thread terpisah
    mqtt_thread = threading.Thread(target=start_mqtt_client, daemon=True)
    mqtt_thread.start()
    
    # Start timer update thread
    timer_thread = threading.Thread(target=update_timer, daemon=True)
    timer_thread.start()
    
    print("🚀 Web interface akan tersedia di: http://localhost:5000")
    print("📊 API Endpoints:")
    print("   - GET /api/timer - Data semua lintasan")
    print("   - GET /api/timer/1 - Data lintasan 1")
    print("   - GET /api/timer/2 - Data lintasan 2")
    print("   - POST /api/reset - Reset semua lintasan")
    print("   - POST /api/reset/1 - Reset lintasan 1")
    print("   - POST /api/reset/2 - Reset lintasan 2")
    
    # Start Flask web server
    app.run(host=WEB_HOST, port=WEB_PORT, debug=WEB_DEBUG)
