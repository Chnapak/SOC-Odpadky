#include <WiFi.h>
#include <WebServer.h>

const char* ssid = "SOČ-Odpadky";
const char* password = "12345678";

WebServer server(80);

// Pick 4 output GPIOs that EXIST on your board headers.
// Change these to match the pins you actually have.
static const int motorLowerIN1 = 16;
static const int motorLowerIN2 = 17;
static const int motorLowerIN3 = 18;
static const int motorLowerIN4 = 19;

static const int motorUpperIN1 = 27;
static const int motorUpperIN2 = 26;
static const int motorUpperIN3 = 25;
static const int motorUpperIN4 = 33;

static const int Button_S1 = 22;

static const int RED_LED = 15;

static const long STEPS_PER_REV = 4096;

// Half-step sequence (8 states) for 28BYJ-48 + ULN2003
const uint8_t SEQ[8][4] = {
  {1,0,0,0},
  {1,1,0,0},
  {0,1,0,0},
  {0,1,1,0},
  {0,0,1,0},
  {0,0,1,1},
  {0,0,0,1},
  {1,0,0,1}
};

volatile long startAngle = 0;
volatile long pendingStepLower = 0;          
volatile long pendingStepUpper = 0;          
volatile unsigned int stepIntervalUs = 900; 
int seqIndexLower = 0;
int seqIndexUpper = 0;
unsigned long lastStepUsLower = 0;
unsigned long lastStepUsUpper = 0;

bool upperStartedForThisMove = false;
bool lowerStoppedMovingForThisMove = false;
bool upperReturnStartedForThisMove = false;
bool upperReturning = false;
long upperMoveStepsForThisMove = 0;

static const long TRIGGER_ANGLE_DEG = 60;
static const long TRIGGER_STEPS = (STEPS_PER_REV * TRIGGER_ANGLE_DEG) / 360;

void applyStepLower(int idx) {
  digitalWrite(motorLowerIN1, SEQ[idx][0]);
  digitalWrite(motorLowerIN2, SEQ[idx][1]);
  digitalWrite(motorLowerIN3, SEQ[idx][2]);
  digitalWrite(motorLowerIN4, SEQ[idx][3]);
}

void applyStepUpper(int idx) {
  digitalWrite(motorUpperIN1, SEQ[idx][0]);
  digitalWrite(motorUpperIN2, SEQ[idx][1]);
  digitalWrite(motorUpperIN3, SEQ[idx][2]);
  digitalWrite(motorUpperIN4, SEQ[idx][3]);
}

void releaseCoilsLower() {
  digitalWrite(motorLowerIN1, LOW);
  digitalWrite(motorLowerIN2, LOW);
  digitalWrite(motorLowerIN3, LOW);
  digitalWrite(motorLowerIN4, LOW);
}

void releaseCoilsUpper() {
  digitalWrite(motorUpperIN1, LOW);
  digitalWrite(motorUpperIN2, LOW);
  digitalWrite(motorUpperIN3, LOW);
  digitalWrite(motorUpperIN4, LOW);
}


// Tiny helper to pull an integer from JSON-ish text: {"steps":123}
bool extractIntField(const String& body, const char* key, long& out) {
  String s = body;
  int k = s.indexOf(key);
  if (k < 0) return false;
  int colon = s.indexOf(':', k);
  if (colon < 0) return false;

  int i = colon + 1;
  while (i < (int)s.length() && (s[i] == ' ' || s[i] == '\t')) i++;

  String num;
  if (i < (int)s.length() && s[i] == '-') { num += s[i]; i++; }
  while (i < (int)s.length() && isDigit(s[i])) { num += s[i]; i++; }

  if (num.length() == 0) return false;
  out = num.toInt();
  return true;
}

// If body is plain integer => steps
bool parsePlainInt(const String& body, long& out) {
  String s = body;
  s.trim();
  if (s.length() == 0) return false;

  int start = 0;
  if (s[0] == '-') start = 1;
  for (int i = start; i < (int)s.length(); i++) {
    if (!isDigit(s[i])) return false;
  }
  out = s.toInt();
  return true;
}

void handlePing() {
  server.send(200, "text/plain", "pong");
}

void handleData() {
  if (digitalRead(Button_S1) == HIGH || pendingStepLower != 0 || pendingStepUpper != 0) {
    server.send(400, "text/plain", "Machine not expecting input");
    return;
  }

  String body = server.arg("plain");

  Serial.println("=== /data received ===");
  Serial.println(body);
  Serial.println("======================");

  long steps = 0;
  long angle = 0;
  long delayUs = 0;

  if (extractIntField(body, "angle", angle)) {
    // angle -> steps
    long deltaAngle = (angle - startAngle) % 360;
    long unsignedDeltaAngle = (abs(deltaAngle));
    long moveByAngle = 0;

    if (unsignedDeltaAngle > 180) {
      if (deltaAngle > 0) {
        moveByAngle = unsignedDeltaAngle - 360;
      }
      else {
        moveByAngle = 360 - unsignedDeltaAngle;
      }
    }
    else {
      moveByAngle = deltaAngle;
    }

    steps = (long)((double)moveByAngle * (double)STEPS_PER_REV / 360.0);
    startAngle = angle;
  } else {
    server.send(400, "text/plain", "Send steps (e.g. 512) or JSON {\"steps\":512} or a{\"angle\":90}");
    return;
  }

  if (extractIntField(body, "delay_us", delayUs)) {
    if (delayUs < 500) delayUs = 500;
    if (delayUs > 20000) delayUs = 20000;
    stepIntervalUs = (unsigned int)delayUs;
  }

  if (steps==0) {
    noInterrupts();
    pendingStepLower = 0;
    pendingStepUpper = 1365;
    upperStartedForThisMove = true;
    lowerStoppedMovingForThisMove = true;
    upperReturnStartedForThisMove = false;
    upperReturning = false;
    upperMoveStepsForThisMove = 1365;
    interrupts();

  }
  else {
    noInterrupts();
    pendingStepLower = steps;
    pendingStepUpper = 0;
    upperStartedForThisMove = false;
    lowerStoppedMovingForThisMove = false;
    upperReturnStartedForThisMove = false;
    upperReturning = false;
    upperMoveStepsForThisMove = 0;
    interrupts();
  }

  server.send(200, "text/plain", "ok");
}

void runLowerStepperNonBlocking() {
  long s = pendingStepLower;
  if (s == 0) return;

  unsigned long now = micros();
  if ((unsigned long)(now - lastStepUsLower) < stepIntervalUs) return;
  lastStepUsLower = now;

  int dir = (s > 0) ? 1 : -1;

  seqIndexLower = (seqIndexLower + dir) & 7;
  applyStepLower(seqIndexLower);

  pendingStepLower = s - dir;

  if (pendingStepLower == 0) {
    releaseCoilsLower();
    lowerStoppedMovingForThisMove = true;
  }
}

void runUpperStepperNonBlocking() {
  long s = pendingStepUpper;
  if (s == 0) return;

  unsigned long now = micros();
  if ((unsigned long)(now - lastStepUsUpper) < stepIntervalUs) return;
  lastStepUsUpper = now;

  int dir = (s > 0) ? 1 : -1;

  seqIndexUpper = (seqIndexUpper + dir) & 7;
  applyStepUpper(seqIndexUpper);

  pendingStepUpper = s - dir;

  if (pendingStepUpper == 0) {
    releaseCoilsUpper();

    if (upperReturning) {
      upperReturning = false;
      upperStartedForThisMove = false;
      upperReturnStartedForThisMove = false;
      lowerStoppedMovingForThisMove = false;
      upperMoveStepsForThisMove = 0;
    }
  }
}

bool motorIsMoving() {
  return pendingStepLower != 0;
}

void maybeStartUpperMotor() {
  if (upperStartedForThisMove || pendingStepLower == 0) {
    return;
  }

  long remaining = abs(pendingStepLower);

  if (remaining <= TRIGGER_STEPS) {
    upperMoveStepsForThisMove  = 1365;
    pendingStepUpper = upperMoveStepsForThisMove;
    upperStartedForThisMove = true;
  }
}

void maybeReturnUpperMotor() {
  if (!upperStartedForThisMove) return;          // upper never went out
  if (upperReturnStartedForThisMove) return;     // already started return
  if (!lowerStoppedMovingForThisMove) return;    // waiting for the lower part to finish
  if (pendingStepUpper != 0) return;             // waiting for the upper outward move to finish

  pendingStepUpper = -upperMoveStepsForThisMove; // go back to original position
  upperReturnStartedForThisMove = true;
  upperReturning = true;
}

void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(motorLowerIN1, OUTPUT);
  pinMode(motorLowerIN2, OUTPUT);
  pinMode(motorLowerIN3, OUTPUT);
  pinMode(motorLowerIN4, OUTPUT);
  pinMode(motorUpperIN1, OUTPUT);
  pinMode(motorUpperIN2, OUTPUT);
  pinMode(motorUpperIN3, OUTPUT);
  pinMode(motorUpperIN4, OUTPUT);
  pinMode(Button_S1, INPUT_PULLUP);
  pinMode(RED_LED, OUTPUT);
  digitalWrite(RED_LED, LOW);

  releaseCoilsLower();

  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(ssid, password);

  Serial.println(ok ? "AP started" : "AP failed");
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP()); // usually 192.168.4.1

  server.on("/ping", HTTP_GET, handlePing);
  server.on("/data", HTTP_POST, handleData);

  server.onNotFound([]() {
    Serial.print("404: ");
    Serial.println(server.uri());
    server.send(404, "text/plain", "not found");
  });

  server.begin();
  Serial.println("HTTP server started on port 80");
}

void loop() {
  server.handleClient();

  maybeStartUpperMotor();
  maybeReturnUpperMotor();

  runLowerStepperNonBlocking();
  runUpperStepperNonBlocking();

  if (pendingStepLower != 0 || pendingStepUpper != 0) {
    digitalWrite(RED_LED, HIGH);
  } else {
    digitalWrite(RED_LED, LOW);
  }
}
