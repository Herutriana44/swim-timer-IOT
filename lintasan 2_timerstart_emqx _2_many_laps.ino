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
#define trigPin 17
#define echoPin 16

// LED
#define ledMerah 5
#define ledHijau 18
#define ledBiru 19

// // untuk lintasan 2 stop
// #define ledMerah 18
// #define ledHijau 5
// #define ledBiru 19

// Buzzer
#define buzzer 15

bool alreadyStarted = false;    
bool finishedFlag = false;      
unsigned long lastStartTime = 0;  // Waktu terakhir start dikirim
unsigned long lastStopTime = 0;   // Waktu terakhir stop diterima
const unsigned long RESET_DELAY = 3000;  // Delay 3 detik setelah stop sebelum bisa start lagi

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

    if (client.connect("ESP32_LANE2_START")) {
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

  if (message == "stop2") {
    alreadyStarted = false;
    finishedFlag = true;
    lastStopTime = millis();  // Catat waktu stop

    Serial.println("RESET - Stop diterima. Siap untuk lap berikutnya.");
    lcd.clear();
    lcd.setCursor(0,0); lcd.print("Jarak: ---");
    lcd.setCursor(0,1); lcd.print("Status: Selesai");

    digitalWrite(ledMerah, LOW);
    digitalWrite(ledHijau, HIGH);
    digitalWrite(ledBiru, LOW);
    buzzerBeep(300);
    
    // Reset finishedFlag setelah delay untuk memungkinkan start lagi
    // Flag akan direset di loop() setelah RESET_DELAY
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

  // Reset finishedFlag setelah delay untuk memungkinkan start lagi (multiple laps)
  if (finishedFlag && lastStopTime > 0 && (millis() - lastStopTime >= RESET_DELAY)) {
    finishedFlag = false;
    lastStopTime = 0;
    Serial.println("✅ Reset finishedFlag - Siap untuk lap berikutnya!");
    
    // Kembalikan ke status standby
    lcd.clear();
    lcd.setCursor(0,0); lcd.print("Jarak: 0cm");
    lcd.setCursor(0,1); lcd.print("Status: Standby");
    
    digitalWrite(ledMerah, HIGH);
    digitalWrite(ledHijau, LOW);
    digitalWrite(ledBiru, LOW);
  }

  if (millis() - lastDistanceCheck >= distanceInterval) {
    lastDistanceCheck = millis();
    float distance = getDistance();

    if (distance > 0) {
      lcd.setCursor(7,0);
      lcd.print("     ");
      lcd.setCursor(7,0);
      lcd.print(distance,0);
      lcd.print("cm");

      // Bisa start jika: belum started ATAU sudah lewat delay setelah stop
      bool canStart = !alreadyStarted && !finishedFlag;
      
      if (distance > 60 && canStart) {
        client.publish(mqtt_topic, "start2");
        Serial.println("START dikirim! (Lap baru)");
        alreadyStarted = true;
        lastStartTime = millis();

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