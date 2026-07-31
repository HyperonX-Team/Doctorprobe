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

// POST the reading to the backend. Returns the HTTP status code, or
// -1 on transport failure.
static int sendDeviceReading(JsonDocument& doc) {
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
               BACKEND_HOST + ":" + BACKEND_PORT + API_PATH;
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
  Serial.println("[boot] Doctordrobe firmware 1.0.0");

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

  if (!isButtonPressed()) {
    delay(20);
    return;
  }

  Serial.println("[btn] button pressed — taking reading");

  if (!sensorsInitialised) {
    initialiseSensors();
  }

  JsonDocument doc;
  if (!readSensors(doc)) {
    Serial.println("[read] sensor error; keeping LED on for 5s");
    digitalWrite(PIN_LED, HIGH);
    delay(5000);
    digitalWrite(PIN_LED, LOW);
    return;
  }

  int statusCode = sendDeviceReading(doc);

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
