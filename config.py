# Configuration file untuk Swim Timer Web Application

# MQTT Configuration
MQTT_BROKER = "broker.emqx.io"  # MQTT broker publik
MQTT_PORT = 1883
MQTT_TOPIC = "renang/timer"
MQTT_CLIENT_ID = "raspberry_pi_timer"

# Web Server Configuration
WEB_HOST = "0.0.0.0"  # Listen on all interfaces
WEB_PORT = 5000
WEB_DEBUG = False

# Timer Configuration
TIMER_UPDATE_INTERVAL = 0.1  # Update timer setiap 100ms
CONNECTION_TIMEOUT = 5  # Timeout untuk connection status (detik)

# WiFi Configuration (untuk referensi)
WIFI_SSID = "JE_ART 5"
WIFI_PASSWORD = "bubat123"

# Logging Configuration
LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Display Configuration
TIME_FORMAT = "H:M:S"  # Format waktu display
LAP_TIME_FORMAT = "H:M:S"  # Format waktu lap 