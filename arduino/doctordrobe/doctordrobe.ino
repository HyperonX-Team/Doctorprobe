// ------------------------------------------------------------------
// Doctordrobe — ESP32 health analyzer firmware.
//
// Reads the TCS34725 colour sensor (saliva strip colour), the DHT22
// temperature/humidity sensor, and sends the snapshot to the
// Doctordrobe backend over HTTP(S) when the button is pressed.
//
// Board: ESP32 DevKit (default), Arduino framework, ESP32 core 2.0.14.
// Libraries: Adafruit TCS34725, DHT sensor library, ArduinoJson.
// ------------------------------------------------------------------

#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <Adafruit_TCS34725.h>
#include <ArduinoJson.h>

#include "config.h"
#include "secrets.h"

// Sensor objects.
Adafruit_TCS34725 tcs(TCS34725_INTEGRATIONTIME_50MS, TCS34725_GAIN_4X);
DHT dht(PIN_DHT, DHT22);

// Network client selected at compile time by USE_HTTPS.
#if USE_HTTPS
WiFiClientSecure tlsClient;
#else
WiFiClient plainClient;
#endif

// ------------------------------------------------------------------
// State
// ------------------------------------------------------------------

static bool sensorsInitialised = false;
static unsigned long lastButtonReadMs = 0;
static bool lastButtonState = HIGH;

// ------------------------------------------------------------------
// Wi-Fi
// ------------------------------------------------------------------

// Connect to Wi-Fi with retries every 5s, up to WIFI_MAX_RETRIES.
// Returns true when connected.
static bool connectWiFiWithRetry() {
  int attempts = 0;
  while (attempts < WIFI_MAX_RETRIES) {
    Serial.print("[wifi] connecting to ");
    Serial.println(WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_RETRY_DELAY_MS) {
      delay(100);
      Serial.print(".");
    }
    Serial.println();
    if (WiFi.status() == WL_CONNECTED) {
      Serial.print("[wifi] connected, IP: ");
      Serial.println(WiFi.localIP());
      return true;
    }
    attempts++;
    Serial.printf("[wifi] attempt %d/%d failed, retrying in %ds...\n",
                  attempts, WIFI_MAX_RETRIES, WIFI_RETRY_DELAY_MS / 1000);
    delay(WIFI_RETRY_DELAY_MS);
  }
  Serial.println("[wifi] giving up; will retry in the main loop");
  return false;
}

// ------------------------------------------------------------------
// NTP time sync (required for TLS certificate validation over HTTPS)
// ------------------------------------------------------------------

static void syncTimeViaNTP() {
#if USE_HTTPS
  Serial.println("[ntp] syncing time...");
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  int retries = 0;
  while (time(nullptr) < 1600000000 && retries < 10) {  // roughly 2020+
    delay(500);
    retries++;
  }
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    char buf[64];
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &timeinfo);
    Serial.printf("[ntp] time synced: %s\n", buf);
  } else {
    Serial.println("[ntp] time sync failed (TLS may reject certificates)");
  }
#else
  (void)0;  // No-op over plain HTTP.
#endif
}

// ------------------------------------------------------------------
// Sensors
// ------------------------------------------------------------------

static void initialiseSensors() {
  if (tcs.begin()) {
    Serial.println("[sensor] TCS34725 found");
  } else {
    Serial.println("[sensor] TCS34725 not found — check I2C wiring (SDA=21, SCL=22)");
  }
  dht.begin();
  sensorsInitialised = true;
}

// Convert a 0..1 raw colour channel to a 0..255 int.
static int rgbToInt(float channel) {
  int value = (int)(channel * 255.0f);
  return constrain(value, 0, 255);
}

// Read all sensors and serialise into a JSON document.
// Returns false when a sensor read fails.
static bool readSensors(JsonDocument& doc) {
  uint16_t r, g, b, c;
  tcs.getRawData(&r, &g, &b, &c);
  if (c == 0) {
    Serial.println("[sensor] colour read failed (clear channel is zero)");
    return false;
  }

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("[sensor] DHT read failed");
    temperature = -1.0f;
    humidity = -1.0f;
  }

  doc["device_id"] = DEVICE_ID;
  doc["rgb_r"] = rgbToInt(r / (float)c);
  doc["rgb_g"] = rgbToInt(g / (float)c);
  doc["rgb_b"] = rgbToInt(b / (float)c);
  doc["temperature_c"] = temperature;
  doc["humidity_pct"] = humidity;
  return true;
}

// ------------------------------------------------------------------
// Backend communication
// ------------------------------------------------------------------

#if USE_HTTPS
// Configure the TLS client. Uses the ESP32 trust bundle by default
// (Amazon roots), which covers most public CAs.
static void configureTLS() {
  tlsClient.setCACertBundle(nullptr);
  tlsClient.setTimeout(HTTP_TIMEOUT_MS / 1000);
}
#endif

// POST a JSON document to a backend path. Returns the HTTP status
// code, or -1 on transport failure.
static int postToBackend(JsonDocument& doc, const char* path) {
#if USE_HTTPS
  configureTLS();
  WiFiClient& client = tlsClient;
#else
  WiFiClient& client = plainClient;
#endif

  HTTPClient http;
  http.setTimeout(HTTP_TIMEOUT_MS);
  http.setConnectTimeout(HTTP_TIMEOUT_MS);
  http.setReuse(false);

  String url = String(USE_HTTPS ? "https://" : "http://") +
               BACKEND_HOST + ":" + BACKEND_PORT + path;
  Serial.println("[http] POST " + url);

  if (!http.begin(client, url)) {
    Serial.println("[http] begin() failed");
    return -1;
  }

  // Device authentication header — define DEVICE_API_KEY in secrets.h
  // when the backend enforces the X-API-Key header.
#ifdef DEVICE_API_KEY
  http.addHeader("X-API-Key", DEVICE_API_KEY);
#endif

  http.addHeader("Content-Type", "application/json");
  http.addHeader("User-Agent", "Doctordrobe/1.0 (ESP32)");

  String payload;
  serializeJson(doc, payload);
  int statusCode = http.POST(payload);

  if (statusCode > 0) {
    Serial.printf("[http] response: %d\n", statusCode);
    String response = http.getString();
    if (response.length() > 0) {
      Serial.println("[http] body: " + response);
    }
  } else {
    Serial.printf("[http] transport error: %s\n", http.errorToString(statusCode).c_str());
  }

  http.end();
  return statusCode;
}

// ------------------------------------------------------------------
// Calibration mode
//
// Serial commands:
//   CAL <analyte> <concentration>   e.g. CAL glucose 3.5
//   CAL BLANK                       capture an unstained strip (white
//                                   balance for this unit)
//   CALCLEAR                        clears the armed calibration
// When armed, the next button press captures CAL_CAPTURES averaged
// sensor readings and posts one labeled sample to /api/calibration/
// samples (or the blank baseline to /api/devices/baseline).
// ------------------------------------------------------------------

static char calAnalyte[CAL_ANALYTE_MAX_LEN] = {0};
static float calConcentration = -1.0f;
static bool calBlankArmed = false;

static void handleSerialCommands() {
  while (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line == "CAL BLANK") {
      calBlankArmed = true;
      calAnalyte[0] = '\0';
      calConcentration = -1.0f;
      Serial.println("[cal] blank armed — place an UNSTAINED strip and press the button");
    } else if (line.startsWith("CAL ")) {
      int space = line.indexOf(' ', 4);
      if (space > 4) {
        String analyte = line.substring(4, space);
        float value = line.substring(space + 1).toFloat();
        if (value > 0.0f && analyte.length() < CAL_ANALYTE_MAX_LEN) {
          analyte.toCharArray(calAnalyte, sizeof(calAnalyte));
          calConcentration = value;
          calBlankArmed = false;
          Serial.printf("[cal] armed: %s = %.3f — press the button to capture\n",
                        calAnalyte, calConcentration);
          return;
        }
      }
      Serial.println("[cal] usage: CAL <analyte> <concentration> | CAL BLANK");
    } else if (line == "CALCLEAR") {
      calAnalyte[0] = '\0';
      calConcentration = -1.0f;
      calBlankArmed = false;
      Serial.println("[cal] cleared");
    }
  }
}

// Average CAL_CAPTURES readings and fill device_id + rgb channels
// (normalized against the clear channel, same as readSensors).
// Returns false on sensor failure.
static bool captureAveragedRgb(JsonDocument& doc) {
  long rSum = 0, gSum = 0, bSum = 0;
  bool ok = true;

  for (int i = 0; i < CAL_CAPTURES; i++) {
    uint16_t r, g, b, c;
    tcs.getRawData(&r, &g, &b, &c);
    if (c == 0) {
      ok = false;
      break;
    }
    rSum += r;
    gSum += g;
    bSum += b;
    if (i < CAL_CAPTURES - 1) {
      delay(CAL_INTERVAL_MS);
    }
  }
  if (!ok) {
    return false;
  }

  float r = rSum / (float)CAL_CAPTURES;
  float g = gSum / (float)CAL_CAPTURES;
  float b = bSum / (float)CAL_CAPTURES;
  float c = (r + g + b) / 3.0f;  // clear is not exposed; approximate
  if (c < 1.0f) {
    return false;
  }

  doc["device_id"] = DEVICE_ID;
  doc["rgb_r"] = rgbToInt(r / c);
  doc["rgb_g"] = rgbToInt(g / c);
  doc["rgb_b"] = rgbToInt(b / c);
  return true;
}

// Average CAL_CAPTURES readings of a control standard and serialise
// one labeled sample. Returns false on sensor failure.
static bool captureCalibrationSample(JsonDocument& doc) {
  long rSum = 0, gSum = 0, bSum = 0;
  float tSum = 0.0f, hSum = 0.0f;
  bool ok = true;

  for (int i = 0; i < CAL_CAPTURES; i++) {
    uint16_t r, g, b, c;
    tcs.getRawData(&r, &g, &b, &c);
    if (c == 0) {
      ok = false;
      break;
    }
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    if (isnan(temperature) || isnan(humidity)) {
      temperature = -1.0f;
      humidity = -1.0f;
    }
    rSum += r;
    gSum += g;
    bSum += b;
    tSum += temperature;
    hSum += humidity;
    if (i < CAL_CAPTURES - 1) {
      delay(CAL_INTERVAL_MS);
    }
  }
  if (!ok) {
    return false;
  }

  // Average then normalize the clear channel (same as readSensors).
  float r = rSum / (float)CAL_CAPTURES;
  float g = gSum / (float)CAL_CAPTURES;
  float b = bSum / (float)CAL_CAPTURES;
  float c = (r + g + b) / 3.0f;  // clear is not exposed; approximate
  if (c < 1.0f) {
    return false;
  }

  doc["device_id"] = DEVICE_ID;
  doc["analyte"] = calAnalyte;
  doc["concentration"] = calConcentration;
  doc["rgb_r"] = rgbToInt(r / c);
  doc["rgb_g"] = rgbToInt(g / c);
  doc["rgb_b"] = rgbToInt(b / c);
  doc["temperature_c"] = tSum / (float)CAL_CAPTURES;
  doc["humidity_pct"] = hSum / (float)CAL_CAPTURES;
  return true;
}

// ------------------------------------------------------------------
// Button handling (debounced)
// ------------------------------------------------------------------

static bool isButtonPressed() {
  bool pressed = (digitalRead(PIN_BUTTON) == LOW);
  if (pressed && lastButtonState != pressed &&
      (millis() - lastButtonReadMs) > BUTTON_DEBOUNCE_MS) {
    lastButtonReadMs = millis();
    lastButtonState = pressed;
    return true;
  }
  if (!pressed) {
    lastButtonState = HIGH;
  }
  return false;
}

// Blink the status LED n times.
static void blinkLed(int times, int periodMs) {
  for (int i = 0; i < times; i++) {
    digitalWrite(PIN_LED, HIGH);
    delay(periodMs / 2);
    digitalWrite(PIN_LED, LOW);
    delay(periodMs / 2);
  }
}

// ------------------------------------------------------------------
// Arduino entry points
// ------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("[boot] Doctordrobe firmware 1.1.0 (calibration mode)");

  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);

  initialiseSensors();
  connectWiFiWithRetry();
  syncTimeViaNTP();
}

void loop() {
  // Reconnect automatically when the network drops.
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[wifi] connection lost, reconnecting...");
    if (!connectWiFiWithRetry()) {
      delay(WIFI_RETRY_DELAY_MS);
      return;
    }
    syncTimeViaNTP();
  }

  handleSerialCommands();

  if (!isButtonPressed()) {
    delay(20);
    return;
  }

  if (!sensorsInitialised) {
    initialiseSensors();
  }

  // Calibration captures take priority over a normal reading.
  if (calBlankArmed) {
    Serial.println("[cal] capturing blank baseline...");
    JsonDocument doc;
    if (!captureAveragedRgb(doc)) {
      Serial.println("[cal] sensor error during blank capture; LED on for 5s");
      digitalWrite(PIN_LED, HIGH);
      delay(5000);
      digitalWrite(PIN_LED, LOW);
      return;
    }
    int statusCode = postToBackend(doc, BASELINE_PATH);
    if (statusCode == 200 || statusCode == 201) {
      Serial.println("[cal] blank baseline accepted — blinking LED 3x");
      blinkLed(3, 300);
    } else {
      Serial.printf("[cal] blank rejected (%d) — LED on for 5s\n", statusCode);
      digitalWrite(PIN_LED, HIGH);
      delay(5000);
      digitalWrite(PIN_LED, LOW);
    }
    calBlankArmed = false;
    Serial.println("[cal] blank disarmed");
    return;
  }

  if (calConcentration > 0.0f) {
    Serial.printf("[cal] capturing %d readings for %s = %.3f...\n",
                  CAL_CAPTURES, calAnalyte, calConcentration);
    JsonDocument doc;
    if (!captureCalibrationSample(doc)) {
      Serial.println("[cal] sensor error during capture; LED on for 5s");
      digitalWrite(PIN_LED, HIGH);
      delay(5000);
      digitalWrite(PIN_LED, LOW);
      return;
    }
    int statusCode = postToBackend(doc, CALIBRATION_PATH);
    if (statusCode == 200 || statusCode == 201) {
      Serial.println("[cal] sample accepted — blinking LED 3x");
      blinkLed(3, 300);
    } else {
      Serial.printf("[cal] sample rejected (%d) — LED on for 5s\n", statusCode);
      digitalWrite(PIN_LED, HIGH);
      delay(5000);
      digitalWrite(PIN_LED, LOW);
    }
    // One shot per CAL command; re-arm for the next concentration.
    calAnalyte[0] = '\0';
    calConcentration = -1.0f;
    Serial.println("[cal] disarmed — send another CAL command for the next sample");
    return;
  }

  Serial.println("[btn] button pressed — taking reading");

  JsonDocument doc;
  if (!readSensors(doc)) {
    Serial.println("[read] sensor error; keeping LED on for 5s");
    digitalWrite(PIN_LED, HIGH);
    delay(5000);
    digitalWrite(PIN_LED, LOW);
    return;
  }

  int statusCode = postToBackend(doc, API_PATH);

  if (statusCode == 200 || statusCode == 201) {
    Serial.println("[ok] reading accepted — blinking LED 3x");
    blinkLed(3, 300);
  } else {
    Serial.printf("[fail] status=%d — LED on for 5s\n", statusCode);
    digitalWrite(PIN_LED, HIGH);
    delay(5000);
    digitalWrite(PIN_LED, LOW);
  }
}
