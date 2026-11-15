// Phone station status LED for an Arduino UNO (built-in LED, pin 13). Not tested on hardware in this project.
// Protocol: 115200 baud, one ASCII byte per state change from scripts/replay_phone_station_uno.py.
//   R READY: off            B BUSY: on                 T RETAKE_REQUEST: slow blink (1 Hz)
//   O OK: one long pulse    N NG: three short pulses   V REVIEW: fast blink (5 Hz)    E ERROR: on, steady
// It only shows state. It drives no actuator and makes no inspection decision.
const int LED = LED_BUILTIN;
char state = 'R';
unsigned long changedAt = 0;

void setup() {
  pinMode(LED, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  if (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'R' || c == 'B' || c == 'T' || c == 'O' || c == 'N' || c == 'V' || c == 'E') {
      state = c;
      changedAt = millis();
    }
  }
  unsigned long t = millis() - changedAt;
  bool on = false;
  switch (state) {
    case 'B': case 'E': on = true; break;
    case 'T': on = (t / 500) % 2 == 0; break;
    case 'V': on = (t / 100) % 2 == 0; break;
    case 'O': on = t < 1000; break;
    case 'N': on = t < 900 && (t / 150) % 2 == 0; break;
    default: on = false;
  }
  digitalWrite(LED, on ? HIGH : LOW);
}
