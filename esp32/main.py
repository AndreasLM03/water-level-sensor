import time
import math
import network
import json
import gc
import config
from machine import Pin, I2C
from ads1x15 import ADS1115
from umqtt.robust import MQTTClient

K = config.H1_MM / (config.U1 - config.U0)  # mm pro Volt, aus Kalibrierwerten abgeleitet

# Volumenformel fuer liegende Rundtanks (Kreissegment) statt linearer Naeherung -
# siehe README "Volumenformel". _VOLUME_CORRECTION gleicht die idealisierte
# Geometrie an die reale Herstellerangabe TOTAL_LITERS an (Wandstaerke, Rippen,
# Anschluesse verringern das tatsaechliche Volumen gegenueber der reinen Formel).
_FULL_AREA_MM2 = math.pi * config.TANK_RADIUS_MM ** 2
_THEORETICAL_FULL_LITERS = _FULL_AREA_MM2 * config.TANK_LENGTH_MM * config.TANK_COUNT / 1000000
_VOLUME_CORRECTION = config.TOTAL_LITERS / _THEORETICAL_FULL_LITERS


def liters_from_mm(h_mm):
    r = config.TANK_RADIUS_MM
    h = max(0, min(h_mm, 2 * r))
    if h <= 0:
        return 0
    area_mm2 = r * r * math.acos((r - h) / r) - (r - h) * math.sqrt(2 * r * h - h * h)
    volume_liters = area_mm2 * config.TANK_LENGTH_MM * config.TANK_COUNT / 1000000
    return volume_liters * _VOLUME_CORRECTION

TOPIC_MM = b"zisterne/fuellstand/mm"
TOPIC_LITER = b"zisterne/fuellstand/liter"
TOPIC_PERCENT = b"zisterne/fuellstand/prozent"
TOPIC_STATUS = b"zisterne/status"

ADS_ADDRESS = 0x48
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)
# gain=1 -> +-4.096V Messbereich. Bei 100Ohm-Shunt liegt das Signal bei 0.4-2.0V;
# die Reserve nach oben faengt den <200%-Ueberlastfall der Sonde laut Datenblatt ab.
ads = ADS1115(i2c, address=ADS_ADDRESS, gain=1)


def sensor_present():
    return ADS_ADDRESS in i2c.scan()


def read_voltage(samples=8):
    # Mittelwert mehrerer Messungen daempft elektrisches Rauschen.
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
    # Ohne explizites Timeout blockiert der zugrundeliegende Socket bei jedem
    # publish()/ping() unbegrenzt, falls die TCP-Verbindung nach einem WLAN-Haenger
    # "halb offen" haengen bleibt - das haette bisher kein wdt.feed() retten koennen.
    client.connect(timeout=10)
    return client


def publish_status(client, interval, sensor_ok):
    wlan = network.WLAN(network.STA_IF)
    status = {
        "rssi": wlan.status("rssi"),
        "uptime_s": time.ticks_ms() // 1000,
        "interval_s": interval,
        "sensor_ok": sensor_ok,
        "mem_free": gc.mem_free(),
    }
    client.publish(TOPIC_STATUS, json.dumps(status).encode(), retain=True)


def sleep_with_wdt(seconds, step=5):
    # Der Watchdog-Timeout (120s, siehe boot.py) ist kuerzer als INTERVAL_S (300s).
    # Deshalb hier haeppchenweise schlafen und zwischendurch feed() aufrufen - sonst
    # resettet der Watchdog den ESP32 waehrend eines normalen 5-Minuten-Intervalls.
    remaining = seconds
    while remaining > 0:
        wdt.feed()
        chunk = min(step, remaining)
        time.sleep(chunk)
        remaining -= chunk


def main():
    client = None
    while client is None:
        wdt.feed()
        try:
            client = connect_mqtt()
        except OSError:
            print("MQTT-Broker nicht erreichbar, naechster Versuch in 5s")
            sleep_with_wdt(5)

    while True:
        wdt.feed()
        try:
            if not sensor_present():
                # Kein ADS1115 am I2C-Bus gefunden (z.B. beim Testen ohne angeschlossene
                # Messhardware) - keine Messung versuchen, nur den Status melden.
                publish_status(client, config.INTERVAL_S, sensor_ok=False)
                sleep_with_wdt(config.INTERVAL_S)
                continue

            mm = level_mm()
            liters = round(liters_from_mm(mm))
            percent = round(100 * mm / config.MAX_LEVEL_MM)

            client.publish(TOPIC_MM, str(round(mm)).encode(), retain=True)
            client.publish(TOPIC_LITER, str(liters).encode(), retain=True)
            client.publish(TOPIC_PERCENT, str(percent).encode(), retain=True)
            publish_status(client, config.INTERVAL_S, sensor_ok=True)

        except OSError:
            # Nicht blind MQTT neu verbinden - falls das WLAN selbst weg ist
            # (z.B. Router kurz offline), bringt ein MQTT-Reconnect allein nichts.
            if not network.WLAN(network.STA_IF).isconnected():
                connect_wifi()
            try:
                client = connect_mqtt()
            except OSError:
                time.sleep(5)
                continue

        sleep_with_wdt(config.INTERVAL_S)


main()
