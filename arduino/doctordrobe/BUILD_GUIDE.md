# Doctordrobe Hardware Build Guide

How to buy the parts, wire them up, flash the firmware, and get a working
Doctordrobe device on your desk. The firmware itself is already compiled
and verified (`arduino-cli compile` exit 0, 60% flash).

---

## 1. Parts list (BOM)

| # | Part | Qty | Why | Typical price |
| - | ---- | --- | --- | ------------- |
| 1 | ESP32 DevKit V1 (ESP-WROOM-32) or NodeMCU-32S | 1 | The brain; Wi-Fi + TLS | $5–12 |
| 2 | Adafruit TCS34725 RGB colour sensor (or compatible module) | 1 | Reads the saliva strip colour | $4–8 |
| 3 | DHT22 (AM2302) temperature/humidity sensor | 1 | Ambient compensation for the assay | $3–6 |
| 4 | Tactile push button (momentary, NO) | 1 | Triggers a reading | $0.50 |
| 5 | LED (any colour) + 220 Ω resistor | 1 + 1 | Status feedback (success/fail) | $0.50 |
| 6 | Breadboard + jumper wires (M/F, M/M) | 1 kit | Prototype wiring | $5 |
| 7 | Micro-USB cable (data, not charge-only!) | 1 | Power + flashing | $2 |
| 8 | USB wall adapter or power bank (5 V) | 1 | Off-computer power | $5 |
| 9 | Saliva test strips (any brand, ~50 pack) | 1 | Sample medium | $5–15 |
| 10 | 3D-printed or plastic enclosure (optional) | 1 | Housing (see §8) | $10–20 |

**Budget total: ~$35–45.** Cheapest viable: ESP32 + TCS34725 + button on
a breadboard (~$15).

> **Alternatives**
> - Instead of the TCS34725 module: any I2C colour sensor with a
>   library (e.g. APDS-9960). The firmware targets the TCS34725 API.
> - DHT22 → DHT11 works for demo purposes (less accurate).
> - Use the ESP32's onboard blue LED on GPIO2 → skip part #5.

---

## 2. Tools

- Screwdriver (small, flat or PH0) for the enclosure
- Soldering iron + solder (only for permanent/perfboard assembly; a
  breadboard needs no soldering)
- A computer with the Arduino IDE 2.x or `arduino-cli` (see §6)
- Multimeter (optional, for continuity checks)

---

## 3. Wiring

Firmware pin map (`arduino/doctordrobe/config.h`):

| Sensor / part | ESP32 pin |
| ------------- | --------- |
| TCS34725 SDA | GPIO21 |
| TCS34725 SCL | GPIO22 |
| TCS34725 VCC | 3V3 |
| TCS34725 GND | GND |
| DHT22 DATA | GPIO4 |
| DHT22 VCC | 3V3 |
| DHT22 GND | GND |
| Button leg A | GPIO0 |
| Button leg B | GND |
| LED anode | GPIO2 |
| LED cathode (via 220 Ω) | GND |

```
ESP32 DevKit                    Breadboard
┌────────────┐
│ 3V3 •──────┼─────────┬──────────► TCS34725 VCC, DHT22 VCC
│ GND •──────┼────┬────┴──────────► TCS34725 GND, DHT22 GND, button B
│ GPIO21 SDA─┼────┴────────────────► TCS34725 SDA
│ GPIO22 SCL─┼────────────────────► TCS34725 SCL
│ GPIO4 ─────┼────────────────────► DHT22 DATA
│ GPIO0 ─────┼────────────────────► button A (pull-up built-in)
│ GPIO2 ─────┼───────────/\/\────► LED anode   (220 Ω)
│            │            GND ◄───┘ LED cathode
│ 5V  •      │   (USB powers the board)
└────────────┘
```

> **Notes**
> - GPIO0 doubles as the flash-mode strapping pin. With the button wired
>   as shown (INPUT_PULLUP), holding it during power-up puts the board in
>   flash mode — don't hold it while flashing.
> - The DHT22 module with the built-in pull-up resistor is preferred; if
>   using the bare sensor, add a 10 kΩ pull-up between DATA and 3V3.
> - Keep the strip reading area clean and lit consistently (the firmware
>   normalises RGB against the clear channel, so lighting is compensated).

---

## 4. Assembly steps

1. **Breadboard layout.** Place the ESP32 at the edge of the board so the
   micro-USB port hangs off the side. Seat the TCS34725 and DHT22 modules.
2. **Power rails.** Run 3V3 and GND rails the length of the board.
3. **I2C bus.** Wire SDA→GPIO21, SCL→GPIO22, and power to the TCS34725.
4. **DHT22.** Wire DATA→GPIO4, power, ground.
5. **Button.** One leg to GPIO0, the other to GND.
6. **LED.** Anode to GPIO2 through the 220 Ω resistor; cathode to GND.
7. **Visual check.** Walk the table in §3 line by line before applying
   power. A multimeter in continuity mode catches swapped SDA/SCL.
8. **Power up.** Connect USB. The onboard LED should stay off until the
   button is pressed.

---

## 5. First power-on test (serial)

Open the Serial Monitor at **115200 baud** (Arduino IDE) or
`arduino-cli monitor -p COM3 -c 115200`:

```
[boot] Doctordrobe firmware 1.0.0
[sensor] TCS34725 found
[wifi] connected, IP: 192.168.1.45
```

If you see `TCS34725 not found`, check the I2C wiring (or the module's
address). If Wi-Fi never connects, re-check `config.h` credentials.

---

## 6. Flashing the firmware

### 6.1 One-time toolchain setup

```bash
arduino-cli core update-index
arduino-cli core install esp32:esp32@2.0.14
arduino-cli lib install "Adafruit TCS34725" "DHT sensor library" "ArduinoJson"
```

### 6.2 Configure

```bash
cd arduino/doctordrobe
cp secrets.h.example secrets.h     # set DEVICE_API_KEY if the backend requires it
```

Edit `config.h`: `WIFI_SSID`, `WIFI_PASS`, `BACKEND_HOST`,
`BACKEND_PORT`, `DEVICE_ID` (must match the Device ID in the app), and
`USE_HTTPS`.

### 6.3 Compile and upload

```bash
arduino-cli board list                        # find your COM port
arduino-cli compile --fqbn esp32:esp32:esp32 doctordrobe
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32 doctordrobe
```

(Arduino IDE 2.x: open `arduino/doctordrobe/doctordrobe.ino`, pick the
board "ESP32 Dev Module" + port, click Upload.)

---

## 7. Using the device

1. Start the backend (`docker compose up --build`, or local uvicorn).
2. In the app, verify the Device ID matches `DEVICE_ID` in `config.h`
   (Settings page).
3. Place a saliva strip under the TCS34725.
4. Press the button — the firmware POSTs the reading to
   `/api/devices/reading`.
5. **LED blinks 3×** → accepted. Open the app → **Checkup → Scan with
   Device**.
6. **LED stays on 5 s** → failure. Check the backend logs, `BACKEND_HOST`
   reachability, Wi-Fi, and the `X-API-Key` if enabled.

---

## 8. Enclosure (optional)

- 3D-print a small box (~100×60×30 mm) with: a hole for the sensor window
  (flush with the top so strips slide under), a button cutout, and a
  micro-USB notch.
- Or repurpose a project box / plastic case and cut openings.
- Keep the sensor window clean; test strips sit flat on the glass.
- A diffuser (thin frosted plastic) over the sensor improves reading
  consistency.

---

## 9. Troubleshooting hardware

| Symptom | Cause / fix |
| ------- | ----------- |
| No serial output | Wrong baud, charge-only cable, board in flash mode (unplug/replug) |
| `TCS34725 not found` | SDA/SCL swapped; module not powered; loose jumper |
| Wi-Fi never connects | Wrong SSID/pass in `config.h`; 2.4 GHz only — ESP32 does not see 5 GHz networks |
| LED stays on 5 s after press | Backend unreachable; check host IP/port, firewall, `DEVICE_API_KEY` mismatch |
| Button does nothing | Button legs swapped or not to GND; check GPIO0 with multimeter |
| Reading looks identical every time | Normal — the Beer-Lambert model is deterministic per reading; check the serial log to confirm fresh sensor values |
| DHT read fails (`isnan`) | Check DATA pin + pull-up; DHT22 needs ≥2 s between reads (firmware handles it) |

---

## 10. Bill of materials recap (printable)

**Order this:**
1× ESP32 DevKit V1 · 1× TCS34725 module · 1× DHT22 module · 1× tactile
button · 1× LED + 220 Ω resistor · 1× breadboard + jumpers · 1× micro-USB
data cable · 50× saliva test strips · (optional) enclosure

**Total: ~$35–45**
