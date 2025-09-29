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

// Ultrasonik
#define trigPin 33
#define echoPin 34

// LED
#define ledMerah 12
#define ledHijau 13

bool alreadyStarted = false;

void setup() {
  Serial.begin(9600);
  Serial.println("🏊‍♂️ Swim Timer Start Sensor dengan test.mosquitto.org");
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

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledMerah, OUTPUT);
  pinMode(ledHijau, OUTPUT);

  digitalWrite(ledMerah, HIGH);  // Merah ON saat standby
  digitalWrite(ledHijau, LOW);
  
  Serial.println("🚀 Sensor Start siap!");
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("🔗 Menghubungkan ke MQTT broker...");
    if (client.connect("ESP32_START_MOSQUITTO")) {
      Serial.println(" ✅ Terhubung ke test.mosquitto.org");
      client.subscribe(mqtt_topic);  // Subscribe agar bisa terima "stop"
      Serial.println("📡 Subscribed ke topic: renang/timer");
    } else {
      Serial.print("❌ Gagal konek MQTT. Code: ");
      Serial.print(client.state());
      Serial.println(" Retry dalam 3 detik...");
      delay(3000);
    }
  }
}

// Callback untuk menerima pesan MQTT
void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  message.trim();

  Serial.print("📨 Pesan dari test.mosquitto.org: ");
  Serial.println(message);

  if (message == "stop") {
    alreadyStarted = false;
    Serial.println("🔄 RESET - Stop diterima");
    digitalWrite(ledMerah, HIGH);
    digitalWrite(ledHijau, LOW);
  }
}

long getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  
  long duration = pulseIn(echoPin, HIGH);
  long distance = duration * 0.034 / 2;
  
  return distance;
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  long distance = getDistance();
  
  // Deteksi start (jarak < 30cm)
  if (distance < 30 && !alreadyStarted) {
    alreadyStarted = true;
    
    // Kirim pesan "start" ke MQTT
    client.publish(mqtt_topic, "start");
    Serial.println("🏁 START terdeteksi! Pesan dikirim ke test.mosquitto.org");
    
    // LED hijau nyala, merah mati
    digitalWrite(ledHijau, HIGH);
    digitalWrite(ledMerah, LOW);
    
    delay(1000); // Delay untuk mencegah deteksi berulang
  }
  
  // Reset jika jarak kembali normal
  if (distance >= 30 && alreadyStarted) {
    delay(500); // Tunggu sebentar untuk memastikan
    if (getDistance() >= 30) {
      alreadyStarted = false;
      digitalWrite(ledMerah, HIGH);
      digitalWrite(ledHijau, LOW);
      Serial.println("🔄 Sensor siap untuk deteksi berikutnya");
    }
  }
  
  delay(100); // Update setiap 100ms
}
