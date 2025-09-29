# Configuration file untuk Swim Timer Web Application dengan test.mosquitto.org

# MQTT Configuration - test.mosquitto.org
MQTT_BROKER = "test.mosquitto.org"  # MQTT broker publik test.mosquitto.org
MQTT_PORT = 1883  # Port unencrypted, unauthenticated
MQTT_TOPIC = "renang/timer"
MQTT_CLIENT_ID = "raspberry_pi_timer"

# Alternative MQTT ports available on test.mosquitto.org:
# 1883 : MQTT, unencrypted, unauthenticated (default)
# 1884 : MQTT, unencrypted, authenticated
# 8883 : MQTT, encrypted, unauthenticated
# 8884 : MQTT, encrypted, client certificate required
# 8885 : MQTT, encrypted, authenticated
# 8886 : MQTT, encrypted, unauthenticated
# 8887 : MQTT, encrypted, server certificate deliberately expired
# 8080 : MQTT over WebSockets, unencrypted, unauthenticated
# 8081 : MQTT over WebSockets, encrypted, unauthenticated
# 8090 : MQTT over WebSockets, unencrypted, authenticated
# 8091 : MQTT over WebSockets, encrypted, authenticated

# Authentication (optional - for ports 1884, 8885, 8090, 8091)
# MQTT_USERNAME = "rw"  # read/write access
# MQTT_PASSWORD = "readwrite"
# MQTT_USERNAME = "ro"  # read only access
# MQTT_PASSWORD = "readonly"
# MQTT_USERNAME = "wo"  # write only access
# MQTT_PASSWORD = "writeonly"

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
LAP_TIME_FORMAT = "H:M:S"

# Broker Information
BROKER_INFO = {
    "name": "test.mosquitto.org",
    "description": "Public Eclipse Mosquitto MQTT server for testing",
    "website": "https://test.mosquitto.org/",
    "features": [
        "Unencrypted, unauthenticated (port 1883)",
        "Encrypted options available",
        "WebSocket support",
        "Authentication options",
        "Free for testing purposes"
    ],
    "caveats": [
        "Not intended for production use",
        "May be unstable due to testing",
        "May be slow (runs under valgrind/perf)",
        "WebSocket and TLS support may be unavailable"
    ]
}
