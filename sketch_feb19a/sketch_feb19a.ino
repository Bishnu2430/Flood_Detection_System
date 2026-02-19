#define TRIG_PIN 9
#define ECHO_PIN 10
#define BUZZER_PIN 3
#define FLOAT_PIN 2
#define RAIN_PIN A0

// Ultrasonic settings
const int samples = 5;

void setup() {
  Serial.begin(9600);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(FLOAT_PIN, INPUT_PULLUP);

  digitalWrite(BUZZER_PIN, LOW);
}

float readUltrasonic() {
  long total = 0;
  int valid = 0;

  for (int i = 0; i < samples; i++) {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);

    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);

    long duration = pulseIn(ECHO_PIN, HIGH, 30000);

    float distance = duration * 0.034 / 2;

    if (distance > 2 && distance < 400) {
      total += distance;
      valid++;
    }

    delay(50);
  }

  if (valid > 0) {
    return total / (float)valid;
  } else {
    return -1; // invalid reading
  }
}

void loop() {

  float distance = readUltrasonic();
  int rainValue = analogRead(RAIN_PIN);

  // Float switch logic (LOW = triggered)
  int floatRaw = digitalRead(FLOAT_PIN);
  int floatStatus = (floatRaw == LOW) ? 1 : 0;

  // Simple emergency buzzer logic
  if (floatStatus == 1) {
    digitalWrite(BUZZER_PIN, HIGH);
  } else {
    digitalWrite(BUZZER_PIN, LOW);
  }

  // JSON Output
  Serial.print("{");
  
  Serial.print("\"distance_cm\":");
  Serial.print(distance);

  Serial.print(",\"rain_analog\":");
  Serial.print(rainValue);

  Serial.print(",\"float_status\":");
  Serial.print(floatStatus);

  Serial.println("}");

  delay(1000);
}
