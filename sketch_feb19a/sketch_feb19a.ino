/*
  Agentic Flood Risk Intelligence System
  Arduino Uno R3 - Final Stable Version
*/

#define TRIG_PIN 9
#define ECHO_PIN 10
#define RAIN_PIN A0
#define FLOAT_PIN 7

#define GREEN_LED 4
#define YELLOW_LED 5
#define RED_LED 6
#define BUZZER 8

#define TANK_HEIGHT 50.0   // Adjust according to setup (cm)
#define SAFE_LEVEL 20.0
#define WARNING_LEVEL 35.0

long duration;
float distance;
float waterHeight;

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(FLOAT_PIN, INPUT_PULLUP);

  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  Serial.println("SYSTEM_READY");
}

float getUltrasonicDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  duration = pulseIn(ECHO_PIN, HIGH, 30000); // timeout 30ms

  if (duration == 0) return -1;

  return duration * 0.034 / 2.0;
}

void setSafe() {
  digitalWrite(GREEN_LED, HIGH);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER, LOW);
}

void setWarning() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, HIGH);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER, LOW);
}

void setFlood() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, HIGH);
  digitalWrite(BUZZER, HIGH);
}

void loop() {

  distance = getUltrasonicDistance();

  if (distance > 0) {
    waterHeight = TANK_HEIGHT - distance;
    if (waterHeight < 0) waterHeight = 0;
  }

  int rainValue = analogRead(RAIN_PIN);
  int floatState = digitalRead(FLOAT_PIN);

  bool flood = false;
  bool warning = false;

  // Emergency float override
  if (floatState == LOW) {
    flood = true;
  }

  if (waterHeight > WARNING_LEVEL) {
    flood = true;
  }
  else if (waterHeight > SAFE_LEVEL) {
    warning = true;
  }

  if (flood) setFlood();
  else if (warning) setWarning();
  else setSafe();

  // Structured serial output (JSON-like)
  Serial.print("{");
  Serial.print("\"height\":"); Serial.print(waterHeight);
  Serial.print(",\"rain\":"); Serial.print(rainValue);
  Serial.print(",\"float\":"); Serial.print(floatState);
  Serial.print(",\"status\":");
  
  if (flood) Serial.print("\"CRITICAL\"");
  else if (warning) Serial.print("\"WARNING\"");
  else Serial.print("\"SAFE\"");
  
  Serial.println("}");

  // Listen for backend alert override
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "ALERT_ON") setFlood();
    if (cmd == "ALERT_OFF") setSafe();
  }

  delay(1000);
}
