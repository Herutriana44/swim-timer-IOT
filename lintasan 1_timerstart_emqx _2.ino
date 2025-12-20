#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const char* ssid = "MAKER 2024";
const char* password = "Makerdotindo24";

// Ganti ke Mosquitto broker
// const char* mqtt_server = "test.mosquitto.org";   // bisa juga pakai IP broker kamu
const char* mqtt_server = "broker.emqx.io";   // bisa juga pakai IP broker kamu
const int mqtt_port = 1883;
const char* mqtt_topic = "renang/timer";

WiFiClient timerUnsika3;
PubSubClient client(timerUnsika3);
LiquidCrystal_I2C lcd(0x27, 16, 2);   // Sesuaikan alamat I2C LCD kamu

// Ultrasonik
#define trigPin 16
#define echoPin 17

// LED
#define ledMerah 5
#define ledHijau 18
#define ledBiru 19

// Buzzer
#define buzzer 15

bool alreadyStarted = false;    
bool finishedFlag = false;      

// Untuk millis
unsigned long previousBuzz = 0;
unsigned long buzzDuration = 300;
bool buzzing = false;

unsigned long lastDistanceCheck = 0;
unsigned long distanceInterval = 300;

void buzzerBeep(unsigned long dur = 300) {
  digitalWrite(buzzer, HIGH);
  buzzing = true;
  buzzDuration = dur;
  previousBuzz = millis();
}

void handleBuzzer() {
  if (buzzing && millis() - previousBuzz >= buzzDuration) {
    digitalWrite(buzzer, LOW);
    buzzing = false;
  }
}

void setup() {
  Serial.begin(9600);

  pinMode(trigPin, OUTPUT);
  pinMode(echoPin, INPUT);

  pinMode(ledMerah, OUTPUT);
  pinMode(ledHijau, OUTPUT);
  pinMode(ledBiru, OUTPUT);
  pinMode(buzzer, OUTPUT);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0,0);
  lcd.print("IoT Timer Device");
  buzzerBeep(300);

  // WiFi connect
  WiFi.begin(ssid, password);
  lcd.clear();
  lcd.print("WiFi Connect...");

  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }
  lcd.clear();
  lcd.print("WiFi Connected");

  delay(1000);

  lcd.clear();
  lcd.setCursor(0,0); lcd.print("Jarak: 0cm");
  lcd.setCursor(0,1); lcd.print("Status: Standby");

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  digitalWrite(ledMerah, HIGH);
  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
}

void reconnect() {
  while (!client.connected()) {
    lcd.clear();
    lcd.setCursor(0,0);
    lcd.print("MQTT Connect...");
    Serial.print("MQTT Connect...");

    if (client.connect("ESP32_LANE1_START")) {
      Serial.println(" Terhubung!");
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("MQTT Connected");
      client.subscribe(mqtt_topic);
      delay(1000);
      lcd.clear();
      lcd.setCursor(0,0); lcd.print("Jarak: 0cm");
      lcd.setCursor(0,1); lcd.print("Status: Standby");
    } else {
      Serial.println(" Gagal, retry...");
      lcd.clear();
      lcd.setCursor(0,0);
      lcd.print("MQTT Failed!");
      delay(2000);
    }
  }
}

void callback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (int i = 0; i < length; i++) {
    message += (char)payload[i];
  }
  message.trim();

  if (message == "stop1") {
    alreadyStarted = false;
    finishedFlag = true;   

    Serial.println("RESET - Stop diterima");
    lcd.clear();
    lcd.setCursor(0,0); lcd.print("Jarak: ---");
    lcd.setCursor(0,1); lcd.print("Status: Selesai");

    digitalWrite(ledMerah, LOW);
    digitalWrite(ledHijau, HIGH);
    digitalWrite(ledBiru, LOW);
    buzzerBeep(300);
  }
}

float getDistance() {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000); // timeout 30ms
  if (duration == 0) return -1;
  return (duration / 2.0) / 29.1;
}

void loop() {
  if (!client.connected()) reconnect();
  client.loop();
  handleBuzzer();

  if (millis() - lastDistanceCheck >= distanceInterval) {
    lastDistanceCheck = millis();
    float distance = getDistance();

    if (distance > 0) {
      lcd.setCursor(7,0);
      lcd.print("     ");
      lcd.setCursor(7,0);
      lcd.print(distance,0);
      lcd.print("cm");

      if (distance > 60 && !alreadyStarted && !finishedFlag) {
        client.publish(mqtt_topic, "start1");
        Serial.println("START dikirim!");
        alreadyStarted = true;

        lcd.clear();
        lcd.setCursor(0,0); 
        lcd.print("Jarak: ");
        lcd.print(distance,0); lcd.print("cm");

        lcd.setCursor(0,1); 
        lcd.print("Status: Renang");

        digitalWrite(ledMerah, LOW);
        digitalWrite(ledHijau, LOW);
        digitalWrite(ledBiru, HIGH);
        buzzerBeep(300);
      }
    }
  }
}