#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ================== Konfigurasi WiFi & MQTT ===================
const char* ssid = "MAKER 2024";
const char* password = "Makerdotindo24";
const char* mqtt_server = "broker.emqx.io";
const int mqtt_port = 1883;
const char* mqtt_topic = "renang/timer";

WiFiClient espClient;
PubSubClient client(espClient);
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ================== Pin ===================
// #define ledHijau  19
// #define ledBiru   18
// #define ledMerah  5

// untuk lintasan 2 stop
#define ledMerah 18
#define ledHijau 5
#define ledBiru 19

#define buzzer    15

// UART Ultrasonik Underwater
#define TXD2 17  // TX ke RX sensor
#define RXD2 16  // RX ke TX sensor
#define COM  0x55

bool systemActive = false;
bool irDetected = false;
unsigned long detectionTime = 0;

// ================== Buzzer non-blocking ===================
unsigned long buzzStart = 0;
unsigned long buzzDuration = 0;
bool buzzing = false;

void buzzerBeep(unsigned long dur = 300){
  digitalWrite(buzzer, HIGH);
  buzzStart = millis();
  buzzDuration = dur;
  buzzing = true;
}

void handleBuzzer(){
  if(buzzing && millis() - buzzStart >= buzzDuration){
    digitalWrite(buzzer, LOW);
    buzzing = false;
  }
}

// ================== Fungsi Reset ===================
void resetSystem() {
  systemActive = false;
  irDetected = false;
  detectionTime = 0;

  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
  digitalWrite(ledMerah, HIGH);

  lcd.clear();
  lcd.setCursor(0,0); lcd.print("Device Stop");
  lcd.setCursor(0,1); lcd.print("No swim");

  buzzerBeep(200);
  Serial.println("Sistem di-reset.");
}

// ================== Fungsi MQTT Callback ===================
void callback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  Serial.println("Dari MQTT: " + msg);

  if (msg == "start2") {
    systemActive = true;
    irDetected = false;
    detectionTime = 0;

    digitalWrite(ledMerah, LOW);
    digitalWrite(ledBiru, HIGH);
    digitalWrite(ledHijau, LOW);

    lcd.clear();
    lcd.setCursor(0,0); lcd.print("Swimming...");
    lcd.setCursor(0,1); lcd.print("Dist: --- cm");

    buzzerBeep(300);
    Serial.println("START diterima. Menunggu deteksi sensor.");
  }
  else if (msg == "reset") {
    resetSystem();
  }
}

// ================== Reconnect MQTT ===================
void reconnect() {
  if (!client.connected()) {
    lcd.clear(); 
    lcd.setCursor(0,0); 
    lcd.print("MQTT Connect...");
    
    // Pastikan lampu merah menyala saat mencoba koneksi
    digitalWrite(ledHijau, LOW);
    digitalWrite(ledBiru, LOW);
    digitalWrite(ledMerah, HIGH);
    
    if (client.connect("ESP32_LANE2_STOP")) {
      client.subscribe(mqtt_topic);
      lcd.clear(); 
      lcd.setCursor(0,0); 
      lcd.print("MQTT Connected!");
      Serial.println("Terhubung MQTT & Subscribed!");
      
      // Pastikan lampu merah tetap menyala setelah koneksi
      digitalWrite(ledHijau, LOW);
      digitalWrite(ledBiru, LOW);
      digitalWrite(ledMerah, HIGH);
      
      delay(1000);
      
      // Kembali ke status awal setelah koneksi berhasil
      resetSystem();
    } else {
      // Handle jika koneksi gagal - tetap merah
      digitalWrite(ledHijau, LOW);
      digitalWrite(ledBiru, LOW);
      digitalWrite(ledMerah, HIGH);
      
      lcd.clear();
      lcd.setCursor(0,0); 
      lcd.print("MQTT Failed!");
      lcd.setCursor(0,1); 
      lcd.print("Retrying...");
      Serial.print("MQTT connection failed, rc=");
      Serial.print(client.state());
      Serial.println(" Retrying in 5 seconds...");
      delay(5000);
    }
  }
}

// ================== Fungsi Koneksi WiFi ===================
void connectWiFi() {
  WiFi.begin(ssid, password);
  lcd.clear();
  lcd.setCursor(0,0); lcd.print("WiFi Connecting");
  
  // Pastikan lampu merah menyala saat koneksi WiFi
  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
  digitalWrite(ledMerah, HIGH);
  
  int dot = 0;

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    lcd.setCursor(0,1);
    lcd.print("Status: ");
    lcd.print(dot++ % 4);
  }

  Serial.println("\nWiFi Connected!");
  lcd.clear();
  lcd.setCursor(0,0); lcd.print("WiFi Connected!");
  lcd.setCursor(0,1); lcd.print(WiFi.localIP().toString());
  
  // Tetap merah setelah WiFi terkoneksi
  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
  digitalWrite(ledMerah, HIGH);
  
  delay(1500);
}

// ================== Fungsi Pembacaan Ultrasonik UART ===================
float getDistance() {
  unsigned char buffer_RTT[4] = {0};
  uint8_t CS;
  int Distance = -1;

  Serial2.write(COM);
  delay(100);

  if(Serial2.available() > 0){
    delay(4);
    if(Serial2.read() == 0xFF){    
      buffer_RTT[0] = 0xFF;
      for (int i=1; i<4; i++){
        buffer_RTT[i] = Serial2.read();   
      }
      CS = buffer_RTT[0] + buffer_RTT[1] + buffer_RTT[2];  
      if(buffer_RTT[3] == CS) {
        Distance = (buffer_RTT[1] << 8) + buffer_RTT[2]; // satuan mm
      }
    }
  }

  if (Distance > 0) return Distance / 10.0; // ubah ke cm
  else return -1; // gagal baca
}

// ================== SETUP ===================
void setup() {
  Serial.begin(115200);

  pinMode(ledHijau, OUTPUT);
  pinMode(ledBiru, OUTPUT);
  pinMode(ledMerah, OUTPUT);
  pinMode(buzzer, OUTPUT);

  // Inisialisasi lampu merah menyala sejak awal
  digitalWrite(ledHijau, LOW);
  digitalWrite(ledBiru, LOW);
  digitalWrite(ledMerah, HIGH);

  lcd.init();
  lcd.backlight();
  lcd.setCursor(0,0); lcd.print("Init Device...");
  buzzerBeep(300);

  connectWiFi();

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);

  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);

  resetSystem(); // kondisi awal
}

// ================== LOOP ===================
unsigned long lastIRCheck = 0;
const unsigned long irInterval = 200; // cek tiap 200ms

void loop() {
  // Pastikan MQTT & WiFi aktif
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!client.connected()) reconnect();
  client.loop();
  handleBuzzer();

  // Baca sensor
  if (millis() - lastIRCheck >= irInterval) {
    lastIRCheck = millis();
    float distance = getDistance();

    // Tampilkan jarak di LCD (hanya kalau aktif)
    if (systemActive) {
      lcd.setCursor(0,1);
      lcd.print("Dist: ");
      if (distance != -1) {
        lcd.print(distance, 1);
        lcd.print(" cm   ");
      } else {
        lcd.print("--- cm   ");
      }
    }

    Serial.print("DISTANCE : ");
    Serial.print(distance);
    Serial.println(" cm");

    // Logika deteksi finish
    if (systemActive && (distance != -1)) {
      if (distance < 5) {  // <5 cm dianggap finish
        irDetected = true;
        detectionTime = millis();

        digitalWrite(ledBiru, LOW);
        digitalWrite(ledHijau, HIGH);
        digitalWrite(ledMerah, LOW);

        client.publish(mqtt_topic, "stop2");

        lcd.clear();
        lcd.setCursor(0,0); lcd.print("Finish!");
        lcd.setCursor(0,1); lcd.print("Dist: ");
        lcd.print(distance,1);
        lcd.print(" cm");

        buzzerBeep(500);
        Serial.println("Objek FINISH terdeteksi. Kirim STOP.");
      }
    }
  }

  // Auto-reset setelah 10 detik
  if (irDetected && millis() - detectionTime >= 10000) {
    resetSystem();
  }
}