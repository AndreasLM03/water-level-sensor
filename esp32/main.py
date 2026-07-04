import time
import network
import json
from machine import Pin, I2C
from ads1x15 import ADS1115
from umqtt.robust import MQTTClient

# --- Kalibrierung: BEISPIELWERTE - durch eigene Messung ersetzen (siehe README) ---
U0 = 0.41             # Volt am Shunt bei 0mm Fuellstand (Trockenmessung)
U1 = 1.22             # Volt am Shunt bei bekannter Eintauchtiefe
H1_MM = 1000          # Eintauchtiefe in mm, mit der U1 gemessen wurde
K = H1_MM / (U1 - U0)   # mm pro Volt, daraus abgeleitet

H_OFFSET_MM = 80      # Sonde haengt so viel ueber dem Zisternenboden
MAX_LEVEL_MM = 1900   # Fuellhoehe bei voller Zisterne
TOTAL_LITERS = 5300
LITERS_PER_MM = TOTAL_LITERS / MAX_LEVEL_MM  # lineare Naeherung, siehe README

# Schwellwert fuer die adaptive Messfrequenz - MUSS nach der Installation anhand
# der tatsaechlichen Rauschstreuung kalibriert werden (siehe README "Schwellwert ermitteln")
CHANGE_THRESHOLD_MM = 8

# --- Adaptive Messfrequenz ---
INTERVAL_LONG_S = 300    # Normalfall: alle 5 Minuten
INTERVAL_SHORT_S = 20    # bei starker Aenderung: alle 20s
STABLE_COUNT_TARGET = 5  # so viele ruhige Messungen in Folge, bevor zurueck auf INTERVAL_LONG_S

MQTT_BROKER = "192.168.x.x"
MQTT_USER = "esp32"
MQTT_PASSWORD = "CHANGE_ME"
MQTT_CLIENT_ID = "zisterne-esp32"
TOPIC_MM = b"zisterne/fuellstand/mm"
TOPIC_LITER = b"zisterne/fuellstand/liter"
TOPIC_PERCENT = b"zisterne/fuellstand/prozent"
TOPIC_STATUS = b"zisterne/status"

i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
# gain=1 -> +-4.096V Messbereich. Bei 100Ohm-Shunt liegt das Signal bei 0.4-2.0V;
# die Reserve nach oben faengt den <200%-Ueberlastfall der Sonde laut Datenblatt ab.
ads = ADS1115(i2c, address=0x48, gain=1)


def read_voltage(samples=8):
    # Mittelwert mehrerer Messungen daempft Rauschen, damit CHANGE_THRESHOLD_MM
    # nicht durch elektrisches Rauschen statt durch echte Pegelaenderung ausgeloest wird.
    total = 0.0
    for _ in range(samples):
        raw = ads.read(rate=4, channel1=0)
        total += ads.raw_to_v(raw)
        time.sleep_ms(10)
    return total / samples


def level_mm():
    v = read_voltage()
    mm = (v - U0) * K + H_OFFSET_MM
    return max(0, mm)


def connect_mqtt():
    client = MQTTClient(
        MQTT_CLIENT_ID, MQTT_BROKER, user=MQTT_USER, password=MQTT_PASSWORD, keepalive=60
    )
    client.connect()
    return client


def publish_status(client, interval):
    wlan = network.WLAN(network.STA_IF)
    status = {
        "rssi": wlan.status("rssi"),
        "uptime_s": time.ticks_ms() // 1000,
        "interval_s": interval,
    }
    client.publish(TOPIC_STATUS, json.dumps(status).encode(), retain=True)


def sleep_with_wdt(seconds, step=5):
    # Der Watchdog-Timeout (60s, siehe boot.py) ist kuerzer als INTERVAL_LONG_S (300s).
    # Deshalb hier haeppchenweise schlafen und zwischendurch feed() aufrufen - sonst
    # resettet der Watchdog den ESP32 waehrend eines normalen 5-Minuten-Intervalls.
    remaining = seconds
    while remaining > 0:
        wdt.feed()
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk


def main():
    client = connect_mqtt()
    interval = INTERVAL_LONG_S
    last_mm = None
    stable_count = 0

    while True:
        wdt.feed()
        try:
            mm = level_mm()
            liters = round(mm * LITERS_PER_MM)
            percent = round(100 * mm / MAX_LEVEL_MM)

            client.publish(TOPIC_MM, str(round(mm)).encode(), retain=True)
            client.publish(TOPIC_LITER, str(liters).encode(), retain=True)
            client.publish(TOPIC_PERCENT, str(percent).encode(), retain=True)
            publish_status(client, interval)

            if last_mm is not None and abs(mm - last_mm) > CHANGE_THRESHOLD_MM:
                interval = INTERVAL_SHORT_S
                stable_count = 0
            else:
                stable_count += 1
                if stable_count >= STABLE_COUNT_TARGET:
                    interval = INTERVAL_LONG_S

            last_mm = mm

        except OSError:
            try:
                client = connect_mqtt()
            except OSError:
                time.sleep(5)
                continue

        sleep_with_wdt(interval)


main()
