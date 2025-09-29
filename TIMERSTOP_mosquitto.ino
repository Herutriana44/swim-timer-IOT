#include <WiFi.h>
#include <PubSubClient.h>

// ================== Konfigurasi WiFi & MQTT ===================
const char* ssid = "JE_ART 5";
const char* password = "bubat123";
const char* mqtt_server = "test.mosquitto.org";  // Broker test.mosquitto.org
const int mqtt_port = 1883;  // Port unencrypted, unauthenticated
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
  Serial.println("🔄 Sistem di-reset.");
}

// ================== Callback MQTT ===================
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim(); // buang spasi atau karakter newline
  
  Serial.print("📨 Pesan dari test.mosquitto.org: ");
  Serial.println(msg);

  if (msg == "start") {
    systemActive = true;
    irDetected = false;
    detectionTime = 0;

    digitalWrite(ledHijau, HIGH);  // 🟢 LED hijau nyala
    digitalWrite(ledBiru, LOW);    // 🔵 Pastikan biru mati
    Serial.println("🏊‍♂️ START diterima. Menunggu deteksi IR finish.");
  } 
  else if (msg == "reset") {
    resetSystem();
  }
}

// ================== Reconnect MQTT ===================
void reconnect() {
  while (!client.connected()) {
    Serial.print("🔗 Menghubungkan ke MQTT broker...");
    if (client.connect("ESP32_FINISH_MOSQUITTO")) {
      Serial.println(" ✅ Terhubung ke test.mosquitto.org");
      client.subscribe(mqtt_topic);
      Serial.println("📡 Subscribed ke topic: renang/timer");
    } else {
      Serial.print("❌ Gagal konek MQTT. Code: ");
      Serial.print(client.state());
      Serial.println(" Coba lagi dalam 5 detik");
      delay(5000);
    }
  }
}

// ================== SETUP ===================
void setup() {
  Serial.begin(9600);
  Serial.println("🏊‍♂️ Swim Timer Stop Sensor dengan test.mosquitto.org");
  Serial.println("🌐 Broker: test.mosquitto.org:1883");

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WiFi Terhubung!");
  Serial.print("📡 IP Address: ");
  Serial.println(WiFi.localIP());

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  pinMode(irPin, INPUT);
  pinMode(ledHijau, OUTPUT);
  pinMode(ledBiru, OUTPUT);

  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
  
  Serial.println("🚀 Sensor Stop siap!");
  Serial.println("⏳ Menunggu pesan START dari test.mosquitto.org...");
}

// ================== LOOP ===================
void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Cek deteksi IR hanya jika sistem aktif
  if (systemActive) {
    int irValue = digitalRead(irPin);
    
    // Deteksi IR (nilai LOW = terdeteksi)
    if (irValue == LOW && !irDetected) {
      irDetected = true;
      detectionTime = millis();
      
      // Kirim pesan "stop" ke MQTT
      client.publish(mqtt_topic, "stop");
      Serial.println("🏁 FINISH terdeteksi! Pesan STOP dikirim ke test.mosquitto.org");
      
      // LED biru nyala, hijau mati
      digitalWrite(ledBiru, HIGH);
      digitalWrite(ledHijau, LOW);
      
      // Reset sistem setelah 2 detik
      delay(2000);
      resetSystem();
    }
    
    // Reset deteksi IR jika tidak terdeteksi lagi
    if (irValue == HIGH && irDetected) {
      irDetected = false;
    }
  }
  
  delay(50); // Update setiap 50ms
}
