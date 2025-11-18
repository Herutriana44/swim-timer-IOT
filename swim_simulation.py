import pygame
import random
import time
import threading
import json
from typing import List, Dict, Optional

# Import MQTT
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    print("Warning: paho-mqtt tidak tersedia. Install dengan: pip install paho-mqtt")

# Import configuration dari config_mosquitto.py
try:
    from config_mosquitto import *
except ImportError:
    # Default configuration jika config_mosquitto.py tidak ada
    MQTT_BROKER = "broker.emqx.io"
    MQTT_PORT = 1883
    MQTT_TOPIC = "renang/timer"
    MQTT_TOPIC_LANE1 = "renang/timer/lintasan1"
    MQTT_TOPIC_LANE2 = "renang/timer/lintasan2"
    MQTT_CLIENT_ID = "swim_simulation"

# Inisialisasi Pygame
pygame.init()

# Konstanta
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 600
LANE_WIDTH = 200
LANE_HEIGHT = 500
SWIMMER_WIDTH = 30
SWIMMER_HEIGHT = 20
TRACK_LENGTH = 50  # meter
CHECKPOINT_DISTANCES = [10, 20, 30, 40, 50]  # meter
FPS = 60

# Warna
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 100, 200)
LIGHT_BLUE = (173, 216, 230)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
GRAY = (128, 128, 128)
DARK_BLUE = (0, 50, 100)

class Swimmer:
    def __init__(self, name: str, color: tuple, lane_number: int):
        self.name = name
        self.color = color
        self.lane_number = lane_number
        self.position = 0.0  # posisi dalam meter (0-50)
        self.speed = random.uniform(0.8, 1.2)  # meter per detik
        self.finished = False
        self.start_time = None
        self.checkpoint_times: Dict[int, float] = {}  # {checkpoint_distance: waktu}
        self.finish_time = None
        
    def update(self, delta_time: float):
        """Update posisi perenang"""
        if not self.finished and self.start_time is not None:
            self.position += self.speed * delta_time
            if self.position >= TRACK_LENGTH:
                self.position = TRACK_LENGTH
                self.finished = True
                if self.finish_time is None:
                    self.finish_time = time.time() - self.start_time
    
    def check_checkpoint(self, checkpoint_distance: int, current_time: float):
        """Cek apakah perenang melewati checkpoint"""
        if checkpoint_distance not in self.checkpoint_times:
            if self.position >= checkpoint_distance:
                elapsed_time = current_time - self.start_time
                self.checkpoint_times[checkpoint_distance] = elapsed_time
                return True
        return False
    
    def start(self, start_time: float):
        """Mulai renang"""
        self.start_time = start_time

class SwimmingSimulation:
    def __init__(self, enable_mqtt: bool = True):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Simulasi Renang - 2 Perenang")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        # Buat 2 perenang
        self.swimmers = [
            Swimmer("Perenang 1", RED, 1),
            Swimmer("Perenang 2", GREEN, 2)
        ]
        
        self.running = False
        self.start_time = None
        self.paused = False
        self.pause_start_time = None
        self.total_pause_time = 0.0
        
        # MQTT setup
        self.enable_mqtt = enable_mqtt and MQTT_AVAILABLE
        self.mqtt_client = None
        self.mqtt_connected = False
        
        if self.enable_mqtt:
            self.setup_mqtt()
        
    def draw_lane(self, lane_number: int, swimmer: Swimmer):
        """Gambar lintasan renang"""
        lane_x = 50 + lane_number * (LANE_WIDTH + 50)
        lane_y = 50
        
        # Gambar kolam renang (background)
        pygame.draw.rect(self.screen, LIGHT_BLUE, 
                        (lane_x, lane_y, LANE_WIDTH, LANE_HEIGHT))
        
        # Gambar garis lintasan
        pygame.draw.rect(self.screen, DARK_BLUE, 
                        (lane_x, lane_y, LANE_WIDTH, LANE_HEIGHT), 3)
        
        # Gambar checkpoint lines
        for checkpoint in CHECKPOINT_DISTANCES:
            checkpoint_y = lane_y + (checkpoint / TRACK_LENGTH) * LANE_HEIGHT
            pygame.draw.line(self.screen, YELLOW, 
                           (lane_x, checkpoint_y), 
                           (lane_x + LANE_WIDTH, checkpoint_y), 2)
            # Label checkpoint
            checkpoint_text = self.small_font.render(f"{checkpoint}m", True, BLACK)
            self.screen.blit(checkpoint_text, (lane_x + LANE_WIDTH + 5, checkpoint_y - 10))
        
        # Gambar start line
        pygame.draw.line(self.screen, WHITE, 
                        (lane_x, lane_y), 
                        (lane_x + LANE_WIDTH, lane_y), 3)
        
        # Gambar finish line
        finish_y = lane_y + LANE_HEIGHT
        pygame.draw.line(self.screen, BLACK, 
                        (lane_x, finish_y), 
                        (lane_x + LANE_WIDTH, finish_y), 5)
        
        # Gambar perenang (bounding box)
        if swimmer.start_time is not None:
            swimmer_y = lane_y + (swimmer.position / TRACK_LENGTH) * LANE_HEIGHT
            swimmer_x = lane_x + (LANE_WIDTH - SWIMMER_WIDTH) // 2
            
            # Bounding box perenang
            pygame.draw.rect(self.screen, swimmer.color, 
                           (swimmer_x, swimmer_y - SWIMMER_HEIGHT, 
                            SWIMMER_WIDTH, SWIMMER_HEIGHT))
            pygame.draw.rect(self.screen, BLACK, 
                           (swimmer_x, swimmer_y - SWIMMER_HEIGHT, 
                            SWIMMER_WIDTH, SWIMMER_HEIGHT), 2)
            
            # Nama perenang di atas bounding box
            name_text = self.small_font.render(swimmer.name, True, BLACK)
            name_rect = name_text.get_rect(center=(lane_x + LANE_WIDTH // 2, 
                                                   swimmer_y - SWIMMER_HEIGHT - 15))
            self.screen.blit(name_text, name_rect)
        
        # Label lintasan
        lane_label = self.font.render(f"Lintasan {lane_number}", True, BLACK)
        self.screen.blit(lane_label, (lane_x, lane_y - 40))
    
    def draw_timer(self):
        """Gambar timer utama"""
        if self.start_time is not None and not self.paused:
            elapsed_time = time.time() - self.start_time - self.total_pause_time
            timer_text = f"Timer: {elapsed_time:.2f} detik"
        else:
            timer_text = "Timer: 0.00 detik"
        
        timer_surface = self.font.render(timer_text, True, BLACK)
        self.screen.blit(timer_surface, (WINDOW_WIDTH // 2 - 100, 10))
    
    def draw_checkpoint_times(self):
        """Gambar waktu checkpoint untuk setiap perenang"""
        y_offset = 100
        x_offset = WINDOW_WIDTH - 350
        
        # Header
        header_text = self.font.render("Waktu Checkpoint", True, BLACK)
        self.screen.blit(header_text, (x_offset, y_offset))
        y_offset += 40
        
        for swimmer in self.swimmers:
            # Nama perenang
            name_text = self.small_font.render(swimmer.name, True, swimmer.color)
            self.screen.blit(name_text, (x_offset, y_offset))
            y_offset += 25
            
            # Tampilkan waktu checkpoint
            for checkpoint in CHECKPOINT_DISTANCES:
                if checkpoint in swimmer.checkpoint_times:
                    checkpoint_time = swimmer.checkpoint_times[checkpoint]
                    time_text = f"  {checkpoint}m: {checkpoint_time:.2f}s"
                    time_surface = self.small_font.render(time_text, True, BLACK)
                    self.screen.blit(time_surface, (x_offset, y_offset))
                    y_offset += 20
                else:
                    checkpoint_text = f"  {checkpoint}m: -"
                    checkpoint_surface = self.small_font.render(checkpoint_text, True, GRAY)
                    self.screen.blit(checkpoint_surface, (x_offset, y_offset))
                    y_offset += 20
            
            # Waktu finish
            if swimmer.finished and swimmer.finish_time is not None:
                finish_text = f"  FINISH: {swimmer.finish_time:.2f}s"
                finish_surface = self.small_font.render(finish_text, True, ORANGE)
                self.screen.blit(finish_surface, (x_offset, y_offset))
                y_offset += 20
            
            y_offset += 10
    
    def setup_mqtt(self):
        """Setup MQTT client"""
        if not MQTT_AVAILABLE:
            return
        
        try:
            self.mqtt_client = mqtt.Client(MQTT_CLIENT_ID + "_simulation")
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            print(f"🔗 Menghubungkan ke MQTT broker: {MQTT_BROKER}:{MQTT_PORT}")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"❌ Error setup MQTT: {e}")
            self.enable_mqtt = False
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback ketika terhubung ke MQTT broker"""
        if rc == 0:
            self.mqtt_connected = True
            print("✅ Koneksi MQTT berhasil!")
            # Subscribe ke topic untuk kedua lintasan
            client.subscribe(MQTT_TOPIC_LANE1)
            client.subscribe(MQTT_TOPIC_LANE2)
            print(f"📡 Subscribed ke topic Lintasan 1: {MQTT_TOPIC_LANE1}")
            print(f"📡 Subscribed ke topic Lintasan 2: {MQTT_TOPIC_LANE2}")
        else:
            print(f"❌ Gagal koneksi MQTT dengan code: {rc}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """Callback ketika menerima pesan MQTT"""
        message = msg.payload.decode('utf-8').strip()
        topic = msg.topic
        
        print(f"📨 Pesan MQTT diterima dari {topic}: {message}")
        
        # Tentukan lintasan berdasarkan topic
        lane_num = None
        if topic == MQTT_TOPIC_LANE1:
            lane_num = 1
        elif topic == MQTT_TOPIC_LANE2:
            lane_num = 2
        elif "lintasan1" in topic.lower() or "lane1" in topic.lower():
            lane_num = 1
        elif "lintasan2" in topic.lower() or "lane2" in topic.lower():
            lane_num = 2
        
        if lane_num is None:
            # Jika topic tidak jelas, gunakan heuristik
            if message == "start2" or message == "start":
                # Cari lintasan yang tidak sedang running
                if not self.swimmers[0].start_time or not self.running:
                    lane_num = 1
                elif not self.swimmers[1].start_time or not self.running:
                    lane_num = 2
                else:
                    lane_num = 1  # Default
            else:
                lane_num = 1  # Default
        
        if lane_num and 1 <= lane_num <= len(self.swimmers):
            swimmer = self.swimmers[lane_num - 1]
            
            # Handle pesan start
            if message == "start2" or message == "start":
                if not self.running:
                    self.running = True
                    self.start_time = time.time()
                    for s in self.swimmers:
                        s.start(self.start_time)
                    print(f"🏊‍♂️ Simulasi STARTED dari MQTT (Lintasan {lane_num})")
                elif not swimmer.start_time:
                    swimmer.start(self.start_time)
                    print(f"🏊‍♂️ Perenang {lane_num} STARTED dari MQTT")
            
            # Handle pesan stop
            elif message == "stop":
                if self.running:
                    self.running = False
                    print(f"⏹️ Simulasi STOPPED dari MQTT")
            
            # Handle pesan reset
            elif message == "reset":
                self.reset()
                print(f"🔄 Simulasi RESET dari MQTT")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback ketika terputus dari MQTT broker"""
        self.mqtt_connected = False
        print(f"🔌 Terputus dari MQTT broker dengan code: {rc}")
    
    def publish_checkpoint(self, swimmer: Swimmer, checkpoint_distance: int, checkpoint_time: float):
        """Publish waktu checkpoint ke MQTT"""
        if not self.enable_mqtt or not self.mqtt_connected or not self.mqtt_client:
            return
        
        # Tentukan topic berdasarkan lintasan
        if swimmer.lane_number == 1:
            topic = MQTT_TOPIC_LANE1.replace("/timer/", "/checkpoint/") if "/timer/" in MQTT_TOPIC_LANE1 else f"{MQTT_TOPIC_LANE1}/checkpoint"
        else:
            topic = MQTT_TOPIC_LANE2.replace("/timer/", "/checkpoint/") if "/timer/" in MQTT_TOPIC_LANE2 else f"{MQTT_TOPIC_LANE2}/checkpoint"
        
        # Format pesan JSON
        message = json.dumps({
            "lane": swimmer.lane_number,
            "checkpoint": checkpoint_distance,
            "time": checkpoint_time,
            "timestamp": time.time()
        })
        
        try:
            self.mqtt_client.publish(topic, message)
            print(f"📤 Published checkpoint {checkpoint_distance}m untuk Lintasan {swimmer.lane_number}: {checkpoint_time:.2f}s")
        except Exception as e:
            print(f"❌ Error publish checkpoint: {e}")
    
    def draw_controls(self):
        """Gambar instruksi kontrol"""
        controls = [
            "SPACE: Start/Pause",
            "R: Reset",
            "ESC: Quit"
        ]
        if self.enable_mqtt:
            mqtt_status = "MQTT: Connected" if self.mqtt_connected else "MQTT: Disconnected"
            controls.insert(0, mqtt_status)
        
        y_pos = WINDOW_HEIGHT - 80
        for control in controls:
            control_text = self.small_font.render(control, True, BLACK)
            self.screen.blit(control_text, (10, y_pos))
            y_pos += 25
    
    def handle_events(self):
        """Handle input events"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                
                elif event.key == pygame.K_SPACE:
                    if not self.running:
                        # Start
                        self.running = True
                        self.start_time = time.time()
                        for swimmer in self.swimmers:
                            swimmer.start(self.start_time)
                    else:
                        # Pause/Resume
                        if self.paused:
                            # Resume
                            self.total_pause_time += time.time() - self.pause_start_time
                            self.paused = False
                        else:
                            # Pause
                            self.paused = True
                            self.pause_start_time = time.time()
                
                elif event.key == pygame.K_r:
                    # Reset
                    self.reset()
        
        return True
    
    def reset(self):
        """Reset simulasi"""
        self.running = False
        self.start_time = None
        self.paused = False
        self.pause_start_time = None
        self.total_pause_time = 0.0
        
        for swimmer in self.swimmers:
            swimmer.position = 0.0
            swimmer.speed = random.uniform(0.8, 1.2)
            swimmer.finished = False
            swimmer.start_time = None
            swimmer.checkpoint_times = {}
            swimmer.finish_time = None
    
    def update(self):
        """Update simulasi"""
        if self.running and not self.paused:
            delta_time = self.clock.get_time() / 1000.0  # Convert to seconds
            
            for swimmer in self.swimmers:
                swimmer.update(delta_time)
                
                # Cek checkpoint
                current_time = time.time()
                for checkpoint in CHECKPOINT_DISTANCES:
                    if swimmer.check_checkpoint(checkpoint, current_time):
                        checkpoint_time = swimmer.checkpoint_times[checkpoint]
                        print(f"{swimmer.name} melewati checkpoint {checkpoint}m pada {checkpoint_time:.2f} detik")
                        # Publish checkpoint ke MQTT
                        self.publish_checkpoint(swimmer, checkpoint, checkpoint_time)
    
    def draw(self):
        """Gambar semua elemen"""
        self.screen.fill(WHITE)
        
        # Gambar lintasan dan perenang
        for i, swimmer in enumerate(self.swimmers):
            self.draw_lane(i + 1, swimmer)
        
        # Gambar timer
        self.draw_timer()
        
        # Gambar waktu checkpoint
        self.draw_checkpoint_times()
        
        # Gambar kontrol
        self.draw_controls()
        
        pygame.display.flip()
    
    def run(self):
        """Jalankan simulasi"""
        running = True
        try:
            while running:
                running = self.handle_events()
                self.update()
                self.draw()
                self.clock.tick(FPS)
        finally:
            # Cleanup MQTT
            if self.enable_mqtt and self.mqtt_client:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            pygame.quit()

if __name__ == "__main__":
    simulation = SwimmingSimulation()
    simulation.run()

