#include <WiFi.h>
#include <PubSubClient.h>

const char* ssid = "JE_ART 5";
const char* password = "bubat123";
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
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
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.println("\nWiFi Terhubung!");

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);
  pinMode(ledMerah, OUTPUT);
  pinMode(ledHijau, OUTPUT);

  digitalWrite(ledMerah, HIGH);  // Merah ON saat standby
  digitalWrite(ledHijau, LOW);
}

void reconnect() {
  while (!client.connected()) {
    if (client.connect("ESP32_START")) {
      Serial.println("Terhubung ke MQTT");
      client.subscribe(mqtt_topic);  // Subscribe agar bisa terima "stop"
    } else {
      Serial.println("Gagal konek MQTT. Retry...");
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

  if (message == "stop") {
    alreadyStarted = false;
    Serial.println("RESET - Stop diterima");
    digitalWrite(ledMerah, HIGH);
    digitalWrite(ledHijau, LOW);
  }
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();

  // Cek jarak dari sensor ultrasonik
  digitalWrite(trigPin, LOW); delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH);
  float distance = (duration / 2.0) / 29.1;

  if (distance > 60 && !alreadyStarted) {
    client.publish(mqtt_topic, "start");
    Serial.println("START dikirim!");
    alreadyStarted = true;
    digitalWrite(ledMerah, LOW);
    digitalWrite(ledHijau, HIGH);
  }

  delay(300);
}
