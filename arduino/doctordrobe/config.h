#ifndef CONFIG_H
#define CONFIG_H

// ------------------------------------------------------------------
// Doctordrobe device configuration.
// Copy to `config.h` and edit for your network and backend.
// (This file is already `config.h`; secrets belong in `secrets.h`.)
// ------------------------------------------------------------------

// Wi-Fi credentials.
const char* WIFI_SSID = "your_wifi";
const char* WIFI_PASS = "your_password";

// Backend host/port. Use the LAN IP of the machine running the API for
// local development, or a DNS name behind a reverse proxy in production.
const char* BACKEND_HOST = "192.168.1.100";
const int BACKEND_PORT = 8000;

// Device identifier registered against the user profile in the app.
const char* DEVICE_ID = "doctordrobe_demo_001";

// TLS toggle. When true the firmware connects over HTTPS using
// WiFiClientSecure (NTP time sync is required for certificate checks).
// Requires a valid CA in secrets.h when the backend uses a private CA.
#define USE_HTTPS false

// Pin assignments (ESP32 DevKit).
#define PIN_BUTTON 0      // GPIO0 — onboard boot button or external
#define PIN_LED 2         // GPIO2 — onboard blue LED
#define PIN_DHT 4         // GPIO4 — DHT22 data line

// Behavioural constants.
#define WIFI_MAX_RETRIES 20     // connect attempts (5s apart)
#define WIFI_RETRY_DELAY_MS 5000
#define BUTTON_DEBOUNCE_MS 200
#define DHT_READ_DELAY_MS 2000  // DHT22 min read interval
#define HTTP_TIMEOUT_MS 10000

// Calibration mode: a button press captures CAL_CAPTURES averaged
// readings spaced CAL_INTERVAL_MS apart and posts one labeled sample.
#define CAL_CAPTURES 10
#define CAL_INTERVAL_MS 500
#define CAL_ANALYTE_MAX_LEN 16

// API endpoints (relative to the backend root).
#define API_PATH "/api/devices/reading"
#define CALIBRATION_PATH "/api/calibration/samples"

#endif // CONFIG_H
