#include <WiFi.h>
#include <PubSubClient.h>

// ================== Konfigurasi WiFi & MQTT ===================
const char* ssid = "JE_ART 5";
const char* password = "bubat123";
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
const char* mqtt_topic = "renang/timer";

WiFiClient espClient;
PubSubClient client(espClient);

// ================== Pin ===================
#define irPin     27
#define ledHijau  12
#define ledBiru   14

bool systemActive = false;
bool irDetected = false;
unsigned long detectionTime = 0;

// ================== Fungsi Reset ===================
void resetSystem() {
  systemActive = false;
  irDetected = false;
  detectionTime = 0;

  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
  Serial.println("Sistem di-reset.");
}

// ================== Callback MQTT ===================
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim(); // buang spasi atau karakter newline
  Serial.println("Dari MQTT: " + msg);

  if (msg == "start") {
    systemActive = true;
    irDetected = false;
    detectionTime = 0;

    digitalWrite(ledHijau, HIGH);  // 🟢 LED hijau nyala
    digitalWrite(ledBiru, LOW);    // 🔵 Pastikan biru mati
    Serial.println("START diterima. Menunggu deteksi IR.");
  } 
  else if (msg == "reset") {
    resetSystem();
  }
}

// ================== Reconnect MQTT ===================
void reconnect() {
  while (!client.connected()) {
    Serial.print("Menghubungkan MQTT...");
    if (client.connect("ESP32_FINISH")) {
      client.subscribe(mqtt_topic);
      Serial.println(" Terhubung & Subscribed!");
    } else {
      Serial.print("Gagal, rc=");
      Serial.print(client.state());
      Serial.println(" coba lagi 5 detik");
      delay(5000);
    }
  }
}

// ================== SETUP ===================
void setup() {
  Serial.begin(9600);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi Terhubung!");

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  pinMode(irPin, INPUT);
  pinMode(ledHijau, OUTPUT);
  pinMode(ledBiru, OUTPUT);

  resetSystem(); // Set semua kondisi awal
}

// ================== LOOP ===================
void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  int irState = digitalRead(irPin);
  Serial.print("IR State: ");
  Serial.println(irState);

  if (systemActive && !irDetected && irState == LOW) {
    // Objek terdeteksi oleh IR
    irDetected = true;
    detectionTime = millis();

    digitalWrite(ledHijau, LOW);   // Matikan hijau
    digitalWrite(ledBiru, HIGH);   // Nyalakan biru

    client.publish(mqtt_topic, "stop");  // Kirim STOP ke server

    Serial.println("Objek FINISH terdeteksi. Kirim STOP. LED biru menyala.");
  }

  // Auto-reset setelah 10 detik dari deteksi IR
  if (irDetected && millis() - detectionTime >= 10000) {
    resetSystem();
  }

  delay(200);
}
