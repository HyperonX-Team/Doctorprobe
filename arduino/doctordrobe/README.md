# Doctordrobe ESP32 Firmware

Firmware for the physical Doctordrobe home-health device: reads a saliva
strip with the TCS34725 RGB colour sensor plus a DHT22
temperature/humidity sensor, and posts the snapshot to the backend when
the button is pressed.

## Hardware

| Part            | Connect to ESP32 (DevKit)        |
| --------------- | -------------------------------- |
| TCS34725        | I2C: SDA → GPIO21, SCL → GPIO22, 3V3, GND |
| DHT22           | DATA → GPIO4, 3V3, GND           |
| Button          | GPIO0 ↔ GND (INPUT_PULLUP)       |
| Status LED      | GPIO2 (onboard, or external + resistor) |

## Libraries

Install via the Arduino IDE Library Manager or `arduino-cli`:

| Library                    | Version  |
| -------------------------- | -------- |
| Adafruit TCS34725          | latest   |
| DHT sensor library         | latest   |
| ArduinoJson                | ^7       |

**Board core:** `esp32` by Espressif, version **2.0.14** (Arduino IDE 2.x).

## Configuration

1. Copy `config.h` defaults to match your network:

   - `WIFI_SSID` / `WIFI_PASS`
   - `BACKEND_HOST` / `BACKEND_PORT`
   - `USE_HTTPS` (false for LAN dev, true behind TLS)
   - `DEVICE_ID` — must match the user's Device ID in the app

2. Copy `secrets.h.example` to `secrets.h` and fill in:
   - `DEVICE_API_KEY` — required when the backend sets `DEVICE_API_KEY`
   - `ROOT_CA_PEM` — only when the backend uses a private CA

   `secrets.h` is git-ignored; never commit it.

## Flashing (Arduino CLI)

```bash
arduino-cli core install esp32:esp32@2.0.14
arduino-cli lib install "Adafruit TCS34725" "DHT sensor library" "ArduinoJson"
arduino-cli compile --fqbn esp32:esp32:esp32 doctordrobe
arduino-cli upload -p <PORT> --fqbn esp32:esp32:esp32 doctordrobe
```

## Behaviour

- Boot: connects to Wi-Fi (retry every 5s, up to 20 attempts), syncs NTP
  when `USE_HTTPS` is true (needed for TLS validation).
- Loop: when the button is pressed (debounced), reads the sensors and
  POSTs `{"device_id", "rgb_r", "rgb_g", "rgb_b", "temperature_c",
  "humidity_pct"}` to `/api/devices/reading`.
- Success (HTTP 200/201): LED blinks 3 times.
- Failure: LED stays on for 5 seconds. Network drops trigger automatic
  reconnect with backoff.

> The RGB channels are normalised against the clear channel so readings
> are lighting-independent.
