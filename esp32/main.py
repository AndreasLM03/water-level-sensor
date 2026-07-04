import time
import network
import json
import config
from machine import Pin, I2C
from ads1x15 import ADS1115
from umqtt.robust import MQTTClient

K = config.H1_MM / (config.U1 - config.U0)  # mm pro Volt, aus Kalibrierwerten abgeleitet
LITERS_PER_MM = config.TOTAL_LITERS / config.MAX_LEVEL_MM  # lineare Naeherung, siehe README

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
    mm = (v - config.U0) * K + config.H_OFFSET_MM
    return max(0, mm)


def connect_mqtt():
    client = MQTTClient(
        config.MQTT_CLIENT_ID,
        config.MQTT_BROKER,
        user=config.MQTT_USER,
        password=config.MQTT_PASSWORD,
        keepalive=60,
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
    interval = config.INTERVAL_LONG_S
    last_mm = None
    stable_count = 0

    while True:
        wdt.feed()
        try:
            mm = level_mm()
            liters = round(mm * LITERS_PER_MM)
            percent = round(100 * mm / config.MAX_LEVEL_MM)

            client.publish(TOPIC_MM, str(round(mm)).encode(), retain=True)
            client.publish(TOPIC_LITER, str(liters).encode(), retain=True)
            client.publish(TOPIC_PERCENT, str(percent).encode(), retain=True)
            publish_status(client, interval)

            if last_mm is not None and abs(mm - last_mm) > config.CHANGE_THRESHOLD_MM:
                interval = config.INTERVAL_SHORT_S
                stable_count = 0
            else:
                stable_count += 1
                if stable_count >= config.STABLE_COUNT_TARGET:
                    interval = config.INTERVAL_LONG_S

            last_mm = mm

        except OSError:
            try:
                client = connect_mqtt()
            except OSError:
                time.sleep(5)
                continue

        sleep_with_wdt(interval)


main()
